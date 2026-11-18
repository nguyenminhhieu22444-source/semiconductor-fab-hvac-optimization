"""Train and validate the Bay 1 thermal PINN using simulated ODE trajectories."""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_model import AIR, CONTROL, COOLING, ThermalForcing, thermal_step
from bay1_pinn import (
    FEATURE_HIGH, FEATURE_LOW, HIDDEN_WIDTH, MODEL_PATH, MODEL_VERSION, RESIDUAL_SCALE,
    network_inputs, residual_factor, thermal_forecast, thermal_signature,
)
from bay1_simulation import write_json


MASS = AIR["effective_thermal_mass_kj_k"]
TAU = COOLING["room_coil_time_constant_s"]
GAIN = COOLING["room_coil_feedback_kw_k"]
SETPOINT = CONTROL["target_temp_c"]
RESIDUAL_KW_SCALE = np.array([2.0, 16.0])
COLLOCATION_DELTA = 0.5
PHYSICS_WEIGHT = 0.25


def thermal_derivative(state, forcing):
    temp, coil = state.T
    load, conductance, capacity = forcing.T
    offset = temp - SETPOINT
    target = np.clip(load + GAIN * offset, 0.0, capacity)
    return np.column_stack(((load - conductance * offset - coil) / MASS, (target - coil) / TAU))


def rk4_transition(features):
    """Reference integration with continuously updated coil feedback."""
    state = features[:, :2].copy()
    forcing = features[:, 2:5]
    steps = 120
    step = features[:, 5:6] / steps
    for _ in range(steps):
        k1 = thermal_derivative(state, forcing)
        k2 = thermal_derivative(state + 0.5 * step * k1, forcing)
        k3 = thermal_derivative(state + 0.5 * step * k2, forcing)
        k4 = thermal_derivative(state + step * k3, forcing)
        state += step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    return state


def physical_transition(features):
    return np.asarray([
        thermal_step(temp, coil, ThermalForcing(load + conductance * SETPOINT, conductance, capacity), time)[:2]
        for temp, coil, load, conductance, capacity, time in features
    ])


def sample_features(rng, count):
    features = rng.uniform(FEATURE_LOW, FEATURE_HIGH, (count, len(FEATURE_LOW)))
    # Draw both normal room operation and off-normal cases, including saturated coils.
    normal = np.arange(count) % 2 == 0
    features[normal, 0] = rng.uniform(21.2, 22.8, normal.sum())
    features[normal, 2] = rng.uniform(15.0, 120.0, normal.sum())
    features[normal, 1] = np.clip(features[normal, 2] + rng.normal(0.0, 22.0, normal.sum()), 0.0, 165.0)
    features[:, 5] = rng.uniform(4.0, 119.0, count)
    features[::5, 5] = CONTROL["control_period_s"]
    return features


def forward(inputs, weights):
    w1, b1, w2, b2, w3, b3 = weights
    h1 = np.tanh(inputs @ w1 + b1)
    h2 = np.tanh(h1 @ w2 + b2)
    return h2 @ w3 + b3, (inputs, h1, h2)


def backward(gradient, cache, weights):
    inputs, h1, h2 = cache
    h2_gradient = (gradient @ weights[4].T) * (1.0 - h2**2)
    h1_gradient = (h2_gradient @ weights[2].T) * (1.0 - h1**2)
    return (inputs.T @ h1_gradient, h1_gradient.sum(axis=0), h1.T @ h2_gradient,
            h2_gradient.sum(axis=0), h2.T @ gradient, gradient.sum(axis=0))


def prepare(features):
    minus, plus = features.copy(), features.copy()
    minus[:, 5] -= COLLOCATION_DELTA
    plus[:, 5] += COLLOCATION_DELTA
    variants = (features, minus, plus)
    inputs = np.stack([network_inputs(case) for case in variants], axis=1)
    factor = np.stack([residual_factor(case[:, 5:6]) * RESIDUAL_SCALE for case in variants], axis=1)
    base = np.stack([physical_transition(case) for case in variants], axis=1)
    targets = rk4_transition(features)
    return inputs, factor, base, targets, features[:, 2:5]


def physics_residual(trajectory, forcing):
    center, minus, plus = trajectory.transpose(1, 0, 2)
    scale = np.array([MASS, TAU]) / RESIDUAL_KW_SCALE
    return ((plus - minus) / (2 * COLLOCATION_DELTA) - thermal_derivative(center, forcing)) * scale


def loss_gradient(prediction, targets, forcing):
    center = prediction[:, 0]
    count = len(center)
    data_error = (center - targets) / RESIDUAL_SCALE
    residual = physics_residual(prediction, forcing)
    data_loss = np.mean(data_error**2)
    residual_loss = np.mean(residual**2)
    scaled = residual * PHYSICS_WEIGHT / (count * RESIDUAL_KW_SCALE)
    gradient = np.zeros_like(prediction)
    gradient[:, 0] = data_error / (count * RESIDUAL_SCALE)
    derivative_gradient = scaled * np.array([MASS, TAU]) / (2 * COLLOCATION_DELTA)
    gradient[:, 1] = -derivative_gradient
    gradient[:, 2] = derivative_gradient
    load, conductance, capacity = forcing.T
    raw_target = load + GAIN * (center[:, 0] - SETPOINT)
    gain = GAIN * ((raw_target > 0.0) & (raw_target < capacity))
    gradient[:, 0, 0] += scaled[:, 0] * conductance - scaled[:, 1] * gain
    gradient[:, 0, 1] += scaled[:, 0] + scaled[:, 1]
    return float(data_loss), float(residual_loss), gradient


def validate(features, data, weights):
    inputs, factor, base, targets, forcing = data
    outputs, _ = forward(inputs.reshape(-1, inputs.shape[-1]), weights)
    trajectory = base + factor * outputs.reshape(factor.shape)
    scores = {}
    for name, values in (("physics", base), ("pinn", trajectory)):
        endpoint = runtime_transition(features, weights)[0] if name == "pinn" else values[:, 0]
        err = np.abs(endpoint - targets)
        r = physics_residual(values, forcing) * RESIDUAL_KW_SCALE
        standard60 = features[:, -1] == CONTROL["control_period_s"]
        scores[name] = {
            "temp_mae_c": float(err[:, 0].mean()),
            "temp_p95_c": float(np.quantile(err[:, 0], 0.95)),
            "coil_mae_kw": float(err[:, 1].mean()),
            "coil_p95_kw": float(np.quantile(err[:, 1], 0.95)),
            "temp_mae_60s_c": float(err[standard60, 0].mean()),
            "coil_mae_60s_kw": float(err[standard60, 1].mean()),
            "energy_balance_rmse_kw": float(np.sqrt(np.mean(r[:, 0]**2))),
            "coil_balance_rmse_kw": float(np.sqrt(np.mean(r[:, 1]**2))),
        }
    return scores


def runtime_transition(features, weights):
    outputs, sources = [], []
    for temp, coil, load, conductance, capacity, time in features:
        forcing = ThermalForcing(load + conductance * SETPOINT, conductance, capacity)
        output, source = thermal_forecast(temp, coil, forcing, time, weights)
        outputs.append(output[:2])
        sources.append(source)
    return np.asarray(outputs), sources


def rollout_validation(initial_features, weights):
    features = initial_features.copy()
    features[:, 5] = CONTROL["control_period_s"]
    reference = features[:, :2].copy()
    physical = reference.copy()
    neural = reference.copy()
    fallback_count = 0
    for _ in range(CONTROL["prediction_steps"]):
        features[:, :2] = reference
        reference = rk4_transition(features)
        features[:, :2] = physical
        physical = physical_transition(features)
        features[:, :2] = neural
        neural, sources = runtime_transition(features, weights)
        fallback_count += sources.count("physics_fallback")
    return {
        "physics": {"temp_mae_c": float(np.mean(abs(physical[:, 0] - reference[:, 0]))),
                    "coil_mae_kw": float(np.mean(abs(physical[:, 1] - reference[:, 1])))},
        "pinn": {"temp_mae_c": float(np.mean(abs(neural[:, 0] - reference[:, 0]))),
                 "coil_mae_kw": float(np.mean(abs(neural[:, 1] - reference[:, 1])))},
        "physics_fallback_steps": fallback_count,
        "trajectories": len(features),
    }


def train(seed=42063, epochs=240, train_count=8192, validation_count=2048):
    rng = np.random.default_rng(seed)
    train_data = prepare(sample_features(rng, train_count))
    selection_features = sample_features(rng, validation_count)
    selection = prepare(selection_features)
    evaluation_rng = np.random.default_rng(seed + 1)
    test_features = sample_features(evaluation_rng, validation_count)
    test_data = prepare(test_features)
    width = HIDDEN_WIDTH
    weights = [
        rng.normal(0.0, 1 / np.sqrt(6), (6, width)), np.zeros(width),
        rng.normal(0.0, 1 / np.sqrt(width), (width, width)), np.zeros(width),
        rng.normal(0.0, 0.08, (width, 2)), np.zeros(2),
    ]
    means, variances = ([np.zeros_like(w) for w in weights] for _ in range(2))
    best, best_loss, best_epoch = None, float("inf"), 0
    updates = 0
    for epoch in range(1, epochs + 1):
        shuffled = rng.permutation(train_count)
        rate = 0.0025 * (0.15 + 0.85 * (1.0 - (epoch - 1) / epochs))
        for start in range(0, train_count, 256):
            index = shuffled[start:start + 256]
            inputs, factor, base, targets, forcing = (part[index] for part in train_data)
            raw, cache = forward(inputs.reshape(-1, inputs.shape[-1]), weights)
            prediction = base + factor * raw.reshape(factor.shape)
            _, _, gradient = loss_gradient(prediction, targets, forcing)
            gradients = backward((gradient * factor).reshape(-1, 2), cache, weights)
            updates += 1
            for weight, mean, variance, change in zip(weights, means, variances, gradients):
                mean *= 0.9
                mean += 0.1 * change
                variance *= 0.999
                variance += 0.001 * change**2
                weight -= rate * (mean / (1 - 0.9**updates)) / (np.sqrt(variance / (1 - 0.999**updates)) + 1e-8)
        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            inputs, factor, base, targets, forcing = selection
            raw, _ = forward(inputs.reshape(-1, inputs.shape[-1]), weights)
            error, residual, _ = loss_gradient(base + factor * raw.reshape(factor.shape), targets, forcing)
            score = error + PHYSICS_WEIGHT * residual
            if score < best_loss:
                best, best_loss, best_epoch = [w.copy() for w in weights], score, epoch
            if epoch == 1 or epoch % 40 == 0 or epoch == epochs:
                print(f"Epoch {epoch:3d} | validation data loss {error:.5f} | physics loss {residual:.5f}", flush=True)

    metrics = validate(test_features, test_data, best)
    rollout = rollout_validation(test_features[:512], best)
    for key in ("temp_mae_c", "coil_mae_kw", "temp_mae_60s_c", "coil_mae_60s_kw",
                "energy_balance_rmse_kw", "coil_balance_rmse_kw"):
        if metrics["pinn"][key] >= metrics["physics"][key]:
            raise RuntimeError(f"PINN did not improve held-out {key}. Existing checkpoint kept.")
    if any(rollout["pinn"][key] >= rollout["physics"][key] for key in ("temp_mae_c", "coil_mae_kw")):
        raise RuntimeError("PINN did not improve the six-step rollout. Existing checkpoint kept.")
    record = {
        "model_version": MODEL_VERSION, "thermal_signature": thermal_signature(),
        "training_source": "synthetic_room_coil_ode_rk4", "seed": seed, "train_samples": train_count,
        "validation_samples": validation_count, "test_samples": validation_count, "best_epoch": best_epoch,
        "physics_loss_weight": PHYSICS_WEIGHT, "physics_residual_scales_kw": RESIDUAL_KW_SCALE.tolist(),
        "test_one_step": metrics, "test_six_steps": rollout,
    }
    record.update({key: weight.tolist() for key, weight in zip(("w1", "b1", "w2", "b2", "w3", "b3"), best)})
    write_json(MODEL_PATH, record)
    print(f"Saved {MODEL_PATH.name}")
    print("One-step test:", metrics)
    print("Six-step test:", rollout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=240)
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    train(epochs=args.epochs)
