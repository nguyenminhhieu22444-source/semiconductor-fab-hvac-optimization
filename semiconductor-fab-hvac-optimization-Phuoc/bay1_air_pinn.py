"""PINN screening of pressure and cumulative particles for a proposed fan command."""

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from bay1_model import LIMITS, PRESSURE


MODEL_VERSION = "bay1-air-pinn-1"
MODEL_PATH = Path(__file__).resolve().parent / "02_ai_solution" / "air_pinn_weights.json"
WIDTH = 12
MAX_TIME_RATIO = 4.0
CHANNELS = ("dp", "particle_count", "particles_05")
LOWER = np.array([LIMITS["dp_min"], 0.0, 0.0])
UPPER = np.array([LIMITS["dp_max"], LIMITS["particles_01_max"], LIMITS["particles_05_max"]])


def forward(time_ratios, weights):
    """Dimensionless step response with the initial condition enforced at t=0."""
    inputs = time_ratios.reshape(-1, 1) / 2.0 - 1.0
    w1, b1, w2, b2, w3, b3 = weights
    hidden1 = np.tanh(inputs @ w1 + b1)
    hidden2 = np.tanh(hidden1 @ w2 + b2)
    response = time_ratios / (1.0 + time_ratios) + time_ratios * (hidden2 @ w3 + b3).ravel()
    return response, (inputs, hidden1, hidden2)


@lru_cache(maxsize=1)
def load_air_pinn():
    record = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if record["model_version"] != MODEL_VERSION or record["max_time_ratio"] != MAX_TIME_RATIO:
        raise ValueError("Air PINN checkpoint version mismatch")
    weights = tuple(np.asarray(record[key], dtype=float) for key in ("w1", "b1", "w2", "b2", "w3", "b3"))
    shapes = ((1, WIDTH), (WIDTH,), (WIDTH, WIDTH), (WIDTH,), (WIDTH, 1), (1,))
    error = float(record["max_validation_error_fraction"])
    if tuple(item.shape for item in weights) != shapes or not all(np.isfinite(item).all() for item in weights):
        raise ValueError("Invalid air PINN tensors")
    if not 0.0 < error <= 0.002:
        raise ValueError("Invalid air PINN validation error")
    for item in weights:
        item.setflags(write=False)
    return weights, error


class AirQualityPINN:
    def __init__(self, plant):
        self.plant = plant
        self.weights, self.validation_error = load_air_pinn()

    def forecast(self, u_mau, u_ffu, state, disturbance, dt_sec):
        if not math.isfinite(dt_sec) or dt_sec <= 0.0:
            return None
        airflow = self.plant.air_exchange(u_mau, u_ffu, disturbance)
        removal = airflow.particle_removal_m3_s
        if removal <= 0.0:
            return None
        particle_time = dt_sec * removal / self.plant.volume
        time_ratios = np.array([dt_sec / PRESSURE["time_constant_s"], particle_time])
        if not np.all((time_ratios >= 0.0) & (time_ratios <= MAX_TIME_RATIO)):
            return None
        initial = np.array([state[key] for key in CHANNELS])
        equilibrium = np.array([airflow.pressure_steady_pa, airflow.particle_source_01_s / removal,
                                airflow.particle_source_05_s / removal])
        response, _ = forward(time_ratios, self.weights)
        if not np.isfinite(response).all():
            return None
        response = np.clip(response, 0.0, 1.0)
        change = equilibrium - initial
        predicted = initial + change * response[[0, 1, 1]]
        margin = 2.0 * self.validation_error * abs(change)
        if not np.isfinite(predicted).all() or not np.isfinite(margin).all():
            return None
        flags = (predicted + margin < LOWER) | (predicted - margin > UPPER)
        return dict(zip(CHANNELS, predicted.tolist())), [key for key, flag in zip(CHANNELS, flags) if flag]
