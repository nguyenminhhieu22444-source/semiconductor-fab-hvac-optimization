"""Fit Bay 1's air PINN to the normalized pressure and particle balance."""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_air_pinn import MAX_TIME_RATIO, MODEL_PATH, MODEL_VERSION, WIDTH, forward
from bay1_simulation import write_json


SEED = 84509
TIME_DELTA = 0.0001
PHYSICS_WEIGHT = 0.5


def train():
    rng = np.random.default_rng(SEED)
    shapes = ((1, WIDTH), (WIDTH,), (WIDTH, WIDTH), (WIDTH,), (WIDTH, 1), (1,))
    offsets = np.cumsum([int(np.prod(shape)) for shape in shapes[:-1]])
    initial = [rng.normal(0.0, 0.22, shape) for shape in shapes]
    initial[-2][:] = 0.0
    initial[-1][:] = 0.0

    def unpack(flat):
        return tuple(values.reshape(shape) for values, shape in zip(np.split(flat, offsets), shapes))

    times = np.sort(rng.uniform(TIME_DELTA, MAX_TIME_RATIO - TIME_DELTA, 480))
    # The exact first-order step response supplies synthetic observations.
    observed = -np.expm1(-times)
    coordinates = np.concatenate((times, times + TIME_DELTA, times - TIME_DELTA))
    coefficient = 2 * PHYSICS_WEIGHT / len(times)

    def objective(flat):
        weights = unpack(flat)
        predictions, (inputs, h1, h2) = forward(coordinates, weights)
        center, plus, minus = np.split(predictions, 3)
        data_error = center - observed
        residual = (plus - minus) / (2 * TIME_DELTA) + center - 1.0
        value = np.mean(data_error**2) + PHYSICS_WEIGHT * np.mean(residual**2)
        derivative = coefficient * residual / (2 * TIME_DELTA)
        out_gradient = coordinates[:, None] * np.concatenate((
            2 * data_error / len(times) + coefficient * residual, derivative, -derivative,
        ))[:, None]
        h2_gradient = (out_gradient @ weights[4].T) * (1.0 - h2**2)
        h1_gradient = (h2_gradient @ weights[2].T) * (1.0 - h1**2)
        grads = (inputs.T @ h1_gradient, h1_gradient.sum(axis=0),
                 h1.T @ h2_gradient, h2_gradient.sum(axis=0),
                 h2.T @ out_gradient, out_gradient.sum(axis=0))
        return float(value), np.concatenate([part.ravel() for part in grads])

    result = minimize(
        objective, np.concatenate([part.ravel() for part in initial]), jac=True, method="L-BFGS-B",
        options={"maxiter": 900, "ftol": 1e-15},
    )
    weights = unpack(result.x)
    test_times = np.linspace(0.0, MAX_TIME_RATIO, 10_001)
    predicted, _ = forward(test_times, weights)
    error = abs(predicted + np.expm1(-test_times))
    plus, _ = forward(test_times[1:-1] + TIME_DELTA, weights)
    minus, _ = forward(test_times[1:-1] - TIME_DELTA, weights)
    residual = (plus - minus) / (2 * TIME_DELTA) + predicted[1:-1] - 1.0
    max_error = float(error.max())
    if not 0.0 < max_error <= 0.002 or not np.isfinite(residual).all():
        raise RuntimeError("Air PINN did not meet the normalized simulation error criterion")
    record = {
        "model_version": MODEL_VERSION, "max_time_ratio": MAX_TIME_RATIO,
        "training_source": "synthetic_normalized_pressure_and_particle_ode",
        "training_samples": len(times), "validation_points": len(test_times),
        "validation_mae_fraction": float(error.mean()), "max_validation_error_fraction": max_error,
        "validation_ode_residual_rmse": float(np.sqrt(np.mean(residual**2))),
        "iterations": int(result.nit),
    }
    print(record)
    record.update({key: weight.tolist() for key, weight in zip(("w1", "b1", "w2", "b2", "w3", "b3"), weights)})
    write_json(MODEL_PATH, record)


if __name__ == "__main__":
    train()
