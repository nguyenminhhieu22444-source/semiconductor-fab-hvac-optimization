"""Fit the direct Bay 1 fan policy using physics-MPC demonstrations."""

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_control import AIEnergyOptimizer, FFU_MIN, MAU_MIN
from bay1_model import CleanroomPlant, Disturbance
from bay1_policy import (
    MODEL_PATH, MODEL_VERSION, PERIOD_S, TRAINING_SOURCE, policy_inputs, policy_signature, upcoming_requirements,
)
from bay1_scenarios import generate_scenario_1_standard, generate_scenario_3_summer_heatwave, generate_scenario_5_weekend_maintenance
from bay1_simulation import disturbance_at, scheduled_forecast, write_json


def demonstration(expert, state, disturbance, forecast):
    upcoming, required = upcoming_requirements(expert.plant, disturbance, forecast, PERIOD_S)
    inputs = policy_inputs(expert.plc, state, disturbance, upcoming, required, PERIOD_S)
    result = expert.optimize_setpoints(
        state, disturbance.equipment_kw, disturbance.particles_per_min, dt_sec=PERIOD_S, forecast=forecast,
    )
    return inputs, result


def replay_example(generate, seed):
    scenario = generate(seed=seed)
    plant = CleanroomPlant()
    expert = AIEnergyOptimizer(plant, use_gpr=False)
    for index in range(len(scenario["times_hr"])):
        actual = disturbance_at(scenario, index)
        plan = scheduled_forecast(scenario, index, actual)
        inputs, result = demonstration(expert, plant.sensor_data(actual), actual, plan)
        yield inputs, result
        plant.step(result["u_mau"], result["u_ffu"], actual.equipment_kw, actual.particles_per_min, disturbance=actual)


def varied_conditions(seed, count):
    rng = np.random.default_rng(seed)
    plant = CleanroomPlant()
    expert = AIEnergyOptimizer(plant, use_gpr=False)
    for index in range(count):
        hot = index % 4 == 0
        source = rng.uniform(60, 1_600) if index % 3 else rng.uniform(130_000, 265_000)
        # Decouple deliberate particle-only challenge from the simulated NH3 source.
        amc_multiplier = min(1.0, 650.0 / source)
        actual = Disturbance(
            rng.uniform(4_500, 9_750) / 3600.0, rng.uniform(20, 112), source,
            rng.uniform(33, 38) if hot else rng.uniform(26, 33),
            rng.uniform(65, 86) if hot else rng.uniform(55, 70), amc_multiplier=amc_multiplier,
        )
        p05 = rng.uniform(16.0, 34.5) if source > 1_600 else rng.uniform(0.1, 15.0)
        state = plant.sensor_data(actual) | {
            "temp": rng.uniform(21.6, 22.4), "rh": rng.uniform(40.2, 44.8), "dp": rng.uniform(15.1, 29.0),
            "particle_count": p05 / 0.12, "particles_05": p05,
            "amc_nh3": rng.uniform(0.02, 1.0), "room_coil_kw": rng.uniform(22.0, 100.0),
        }
        expert.plc.failsafe_active = False
        expert.plc.prev_u_mau = float(np.clip(expert.plc.local_pressure_command(actual) + rng.uniform(-0.025, 0.04), MAU_MIN, 1.0))
        expert.plc.prev_u_ffu = rng.uniform(FFU_MIN, 1.0)
        delta = rng.uniform(-0.018, 0.040)
        future = tuple(replace(actual, exhaust_m3_s=actual.exhaust_m3_s + delta * step) for step in range(1, 6))
        yield demonstration(expert, state, actual, future)


def training_arrays(generators):
    features, spread, lower, targets = [], [], [], []
    for rows in generators:
        for (inputs, low, high), command in rows:
            if command["status"] != "SAFE":
                continue
            features.append(inputs)
            spread.append(high - low)
            lower.append(low)
            targets.append([command["u_mau"], command["u_ffu"]])
    return tuple(np.array(data) for data in (features, spread, lower, targets))


def export_tree(regressor):
    tree = regressor.tree_
    return [
        [-1, float(tree.value[i, 0, 0]), -1, -1] if left == right
        else [int(tree.feature[i]), float(tree.threshold[i]), int(left), int(right)]
        for i, (left, right) in enumerate(zip(tree.children_left, tree.children_right))
    ]


def main():
    generators = (generate_scenario_1_standard, generate_scenario_3_summer_heatwave, generate_scenario_5_weekend_maintenance)
    train = [replay_example(generate, 431 + i) for i, generate in enumerate(generators)]
    evaluation = [replay_example(generate, 891 + i) for i, generate in enumerate(generators)]
    x, spread, lower, actions = training_arrays([*train, varied_conditions(540, 3600)])
    holdout_x, holdout_spread, holdout_lower, holdout_actions = training_arrays([*evaluation, varied_conditions(859, 1500)])
    labels = np.divide(actions - lower, spread, out=np.zeros_like(actions), where=spread > 1e-10)
    labels = np.clip(labels, 0, 1)
    trees, predicted = [], []
    for column in range(2):
        regressor = DecisionTreeRegressor(
            criterion="absolute_error", max_depth=7, min_samples_leaf=12, random_state=631,
        ).fit(x, labels[:, column])
        trees.append(export_tree(regressor))
        predicted.append(regressor.predict(holdout_x))
    imitation = holdout_lower + np.column_stack(predicted) * holdout_spread
    errors = abs(imitation - holdout_actions)
    record = {
        "model_version": MODEL_VERSION, "policy_signature": policy_signature(), "training_source": TRAINING_SOURCE,
        "mau_tree": trees[0], "ffu_tree": trees[1],
        "training_samples": len(x), "held_out_samples": len(holdout_x),
        "held_out_mean_absolute_error_pct_points": (100 * errors.mean(axis=0)).tolist(),
        "held_out_p95_absolute_error_pct_points": (100 * np.quantile(errors, 0.95, axis=0)).tolist(),
    }
    write_json(MODEL_PATH, record)
    print({key: value for key, value in record.items() if key not in {"mau_tree", "ffu_tree"}})
    print("Tree nodes (MAU, FFU):", [len(tree) for tree in trees])


if __name__ == "__main__":
    main()
