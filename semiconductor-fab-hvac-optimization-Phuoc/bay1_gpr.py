"""Gaussian-process corrections to Bay 1 pressure and particle forecasts."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from bay1_model import CONFIG, CONTROL


MODEL_PATH = Path(__file__).resolve().parent / "02_ai_solution" / "gpr_model.json"
MODEL_VERSION = "bay1-air-gpr-1"
PRESSURE_KEYS = ("dp",)
PARTICLE_KEYS = ("particle_count", "particles_05")
PERIOD_S = CONTROL["control_period_s"]
MAX_TRAINING_ROWS = 192


def model_signature():
    inputs = [CONFIG[key] for key in ("geometry", "mau", "ffu", "pressure", "contaminants")]
    return hashlib.sha256(json.dumps([inputs, PERIOD_S], sort_keys=True).encode("utf-8")).hexdigest()


def pressure_features(state, prediction, disturbance, u_ffu):
    return np.array([prediction["dp_steady"], state["dp"] - prediction["dp_steady"], disturbance.door_fraction])


def particle_features(state, prediction, disturbance, u_ffu):
    return np.array([
        np.log1p(prediction["particle_count"]), np.log1p(prediction["particles_05"]),
        np.log1p(state["particle_count"]), u_ffu, disturbance.door_fraction,
    ])


def squared_exponential(points, inputs):
    difference = inputs[:, None, :] - points[None, :, :]
    return np.exp(-0.5 * np.sum(difference**2, axis=-1))


class ResidualGP:
    """Zero-mean RBF Gaussian process with shared covariance across residual channels."""

    def __init__(self, record, width, outputs):
        features = np.asarray(record["features"], dtype=float)
        residuals = np.asarray(record["residuals"], dtype=float)
        self.center = np.asarray(record["center"], dtype=float)
        self.scale = np.asarray(record["scale"], dtype=float)
        self.output_scale = np.asarray(record["output_scale"], dtype=float)
        self.interval = np.asarray(record["interval_multiplier"], dtype=float)
        self.noise = float(record["noise"])
        if features.ndim != 2 or not 1 <= len(features) <= MAX_TRAINING_ROWS or features.shape[1] != width:
            raise ValueError("invalid GPR feature shape")
        if residuals.shape != (len(features), outputs):
            raise ValueError("invalid GPR target shape")
        if self.center.shape != (width,) or self.scale.shape != (width,):
            raise ValueError("invalid GPR input scale shape")
        if self.output_scale.shape != (outputs,) or self.interval.shape != (outputs,):
            raise ValueError("invalid GPR output scale shape")
        arrays = (features, residuals, self.center, self.scale, self.output_scale, self.interval)
        if (not all(np.isfinite(values).all() for values in arrays)
                or min(self.scale) <= 0 or min(self.output_scale) <= 0 or min(self.interval) <= 0
                or not 0 < self.noise <= 1):
            raise ValueError("invalid GPR scales or data")

        self.points = (features - self.center) / self.scale
        kernel = squared_exponential(self.points, self.points)
        kernel.flat[::len(kernel) + 1] += self.noise**2
        factor = np.linalg.cholesky(kernel)
        self.inverse_factor = np.linalg.solve(factor, np.eye(len(kernel)))
        self.alpha = self.inverse_factor.T @ (self.inverse_factor @ (residuals / self.output_scale))

    def predict(self, inputs):
        points = (np.atleast_2d(inputs) - self.center) / self.scale
        kernel = squared_exponential(self.points, points)
        mean = kernel @ self.alpha * self.output_scale
        projected = np.einsum("ij,kj->ik", kernel, self.inverse_factor)
        variance = np.maximum(0.0, 1.0 + self.noise**2 - np.sum(projected**2, axis=1))
        deviation = np.sqrt(variance)[:, None] * self.output_scale
        return mean, deviation, kernel.max(axis=1)


@lru_cache(maxsize=1)
def load_model():
    record = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if record["model_version"] != MODEL_VERSION or record["model_signature"] != model_signature():
        raise ValueError("GPR checkpoint does not match Bay 1's model or control period")
    source = record["training_source"]
    if source not in {"measured_csv", "synthetic_alternate_pressure_and_filtration"}:
        raise ValueError("invalid GPR training data source")
    return ResidualGP(record["pressure"], 3, 1), ResidualGP(record["particles"], 5, 2), source


class CleanroomGPR:
    def __init__(self, plant):
        self.plant = plant
        try:
            self.pressure, self.particles, self.training_source = load_model()
        except (OSError, ValueError, TypeError, KeyError, np.linalg.LinAlgError):
            self.training_source = None

    def predict_transition(self, u_mau, u_ffu, state, disturbance, dt_sec):
        prediction = self.plant.predict(u_mau, u_ffu, state, disturbance, dt_sec)
        prediction["prediction_source"] = "physics_fallback"
        if self.training_source is None or dt_sec != PERIOD_S:
            return prediction

        pressure_x = pressure_features(state, prediction, disturbance, u_ffu)
        particle_x = particle_features(state, prediction, disturbance, u_ffu)
        pressure_mean, pressure_std, pressure_support = self.pressure.predict(pressure_x)
        particle_mean, particle_std, particle_support = self.particles.predict(particle_x)
        if min(pressure_support[0], particle_support[0]) < 0.35:
            return prediction

        dp = prediction["dp"] + float(pressure_mean[0, 0])
        dp_margin = float(pressure_std[0, 0] * self.pressure.interval[0])
        particle_center = np.log1p([prediction[key] for key in PARTICLE_KEYS]) + particle_mean[0]
        particle_margin = particle_std[0] * self.particles.interval
        particle_log = np.array([
            particle_center - particle_margin, particle_center, particle_center + particle_margin,
        ])
        if not np.isfinite([dp, dp_margin]).all() or not np.isfinite(particle_log).all():
            return prediction
        particle_low, particles, particle_high = np.expm1(np.clip(particle_log, 0.0, np.log1p(1_000_000.0)))
        # The larger size channel is a subset of the smaller cumulative channel.
        for values in (particle_low, particles, particle_high):
            values[1] = min(values[0], values[1])

        prediction.update(zip(PARTICLE_KEYS, particles.tolist()))
        prediction["dp"] = dp
        prediction["prediction_source"] = "gpr"
        prediction["prediction_bounds"] = {"dp": (dp - dp_margin, dp + dp_margin)}
        prediction["prediction_bounds"].update(zip(PARTICLE_KEYS, zip(particle_low.tolist(), particle_high.tolist())))
        return prediction
