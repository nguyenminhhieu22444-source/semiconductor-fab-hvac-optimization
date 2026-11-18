"""Physics-informed neural correction for Bay 1's room and coil dynamics."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from bay1_model import AIR, CONTROL, COOLING, thermal_step


MODEL_PATH = Path(__file__).resolve().parent / "02_ai_solution" / "pinn_weights.json"
MODEL_VERSION = "bay1-thermal-pinn-1"
FEATURE_CENTER = np.array([22.0, 80.0, 75.0, 4.0, 140.0, 60.0])
FEATURE_SCALE = np.array([3.0, 60.0, 65.0, 1.2, 20.0, 60.0])
FEATURE_LOW = np.array([18.0, 0.0, -15.0, 2.5, 116.0, 0.0])
FEATURE_HIGH = np.array([26.0, 175.0, 175.0, 5.5, 164.0, 120.0])
RESIDUAL_SCALE = np.array([0.15, 8.0])
HIDDEN_WIDTH = 32


def thermal_signature():
    parameters = [AIR, COOLING, CONTROL["target_temp_c"]]
    return hashlib.sha256(json.dumps(parameters, sort_keys=True).encode("utf-8")).hexdigest()


def network_inputs(features):
    return (features - FEATURE_CENTER) / FEATURE_SCALE


def residual_factor(t_sec):
    # The neural correction and its first time derivative vanish at the initial condition.
    return (t_sec / 60.0) ** 2


@lru_cache(maxsize=1)
def load_weights():
    try:
        record = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        if record["model_version"] != MODEL_VERSION or record["thermal_signature"] != thermal_signature():
            raise ValueError("checkpoint version or thermal parameters differ")
        tensors = tuple(np.asarray(record[key], dtype=float) for key in ("w1", "b1", "w2", "b2", "w3", "b3"))
        shapes = ((len(FEATURE_CENTER), HIDDEN_WIDTH), (HIDDEN_WIDTH,), (HIDDEN_WIDTH, HIDDEN_WIDTH),
                  (HIDDEN_WIDTH,), (HIDDEN_WIDTH, 2), (2,))
        if tuple(tensor.shape for tensor in tensors) != shapes or not all(np.isfinite(tensor).all() for tensor in tensors):
            raise ValueError("invalid checkpoint tensors")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError("PINN weights unavailable or incompatible. Run python 02_ai_solution/train_pinn.py.") from error
    for tensor in tensors:
        tensor.setflags(write=False)
    return tensors


def correction(features, tensors):
    w1, b1, w2, b2, w3, b3 = tensors
    hidden = np.tanh(network_inputs(features) @ w1 + b1)
    hidden = np.tanh(hidden @ w2 + b2)
    return (hidden @ w3 + b3) * RESIDUAL_SCALE


def thermal_forecast(temp, coil, forcing, dt_sec, tensors):
    physical = thermal_step(temp, coil, forcing, dt_sec)
    features = np.array([temp, coil, forcing.load_at_setpoint_kw, forcing.conductance_kw_k,
                         forcing.coil_capacity_kw, dt_sec])
    if not np.all((features >= FEATURE_LOW) & (features <= FEATURE_HIGH)):
        return physical, "physics_fallback"
    delta_temp, delta_coil = correction(features, tensors) * residual_factor(dt_sec)
    next_temp = physical[0] + float(delta_temp)
    next_coil = physical[1] + float(delta_coil)
    if not np.isfinite(next_temp) or not np.isfinite(next_coil) or abs(delta_temp) > 1.0 or abs(delta_coil) > 40.0:
        return physical, "physics_fallback"
    maximum = max(coil, forcing.coil_capacity_kw)
    next_coil = max(0.0, min(maximum, next_coil))
    # Recover average cooling from the room energy balance using the temperature endpoints.
    avg_coil = (
        forcing.heat_source_kw - forcing.conductance_kw_k * (temp + next_temp) / 2.0
        - AIR["effective_thermal_mass_kj_k"] * (next_temp - temp) / dt_sec
    )
    return (next_temp, next_coil, max(0.0, min(maximum, avg_coil))), "pinn"


class CleanroomPINN:
    """Forecast a room transition with a trained thermal correction and explicit balances."""

    def __init__(self, plant_model):
        self.plant = plant_model
        self.tensors = load_weights()

    def predict_transition(self, u_mau, u_ffu, state, disturbance, dt_sec):
        mode = "physics_fallback"

        def thermal_transition(temp, coil, forcing, step_sec):
            nonlocal mode
            result, mode = thermal_forecast(temp, coil, forcing, step_sec, self.tensors)
            return result

        prediction = self.plant.predict(
            u_mau, u_ffu, state, disturbance, dt_sec, thermal_transition=thermal_transition,
        )
        prediction["prediction_source"] = mode
        return prediction
