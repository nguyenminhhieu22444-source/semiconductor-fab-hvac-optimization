"""Fit Bay 1 residual Gaussian processes from measured or synthetic transitions."""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_gpr import (
    MAX_TRAINING_ROWS, MODEL_PATH, MODEL_VERSION, PARTICLE_KEYS, PERIOD_S, PRESSURE_KEYS, ResidualGP,
    model_signature, particle_features, pressure_features,
)
from bay1_model import CONTAMINANTS, FFU, MAU, PRESSURE, CleanroomPlant, Disturbance, approach, leakage_flow, well_mixed
from bay1_simulation import write_json


SEED = 58170
CSV_FIELDS = (
    "u_mau", "u_ffu", "exhaust_m3h", "door_fraction", "particle_gen_per_min",
    "dp", "particles_01", "particles_05", "next_dp", "next_particles_01", "next_particles_05",
)


def simulated_target(plant, state, baseline, disturbance, u_mau, u_ffu):
    """Alternate synthetic plant with modest errors in leakage dynamics and filtration."""
    door = disturbance.door_fraction
    net_mau = u_mau * plant.mau_max_airflow
    infiltration = max(0.0, disturbance.exhaust_m3_s - net_mau) + door * PRESSURE["door_mixing_m3_s"]
    outflow = net_mau + infiltration
    ffu_flow = u_ffu * plant.n_ffu * plant.ffu_rated_airflow
    removal = outflow + 0.95 * FFU["particle_efficiency"] * ffu_flow
    pressure = approach(state["dp"], 0.975 * baseline["dp_steady"], 21.0, PERIOD_S)
    generation = 1.17 * disturbance.particles_per_min / 60.0
    particles = [
        well_mixed(state[key], generation * fraction + net_mau * supply + infiltration * corridor,
                   removal, plant.volume, PERIOD_S)
        for key, fraction, supply, corridor in (
            ("particle_count", 1.0, CONTAMINANTS["supply_particles_01_m3"], CONTAMINANTS["corridor_particles_01_m3"]),
            ("particles_05", CONTAMINANTS["generation_fraction_05"],
             CONTAMINANTS["supply_particles_05_m3"], CONTAMINANTS["corridor_particles_05_m3"]),
        )
    ]
    return np.array([pressure, *particles])


def synthetic_samples(plant, count, seed):
    rng = np.random.default_rng(seed)
    minimum_ffu = FFU["min_face_velocity_m_s"] / FFU["rated_face_velocity_m_s"]
    for index in range(count):
        door = rng.uniform(0.05, 1.0) if index % 6 == 0 else 0.0
        u_mau = rng.uniform(MAU["min_command"], 1.0)
        u_ffu = rng.uniform(minimum_ffu, 1.0)
        dp_steady = rng.uniform(-1.0, 12.0) if door else rng.uniform(12.0, 28.0)
        exhaust = max(0.0, u_mau * plant.mau_max_airflow - leakage_flow(dp_steady, door))
        source = rng.uniform(60.0, 1_300.0) if index % 4 else rng.uniform(35_000.0, 210_000.0)
        measured_dp = rng.uniform(12.0, 28.0) if index % 2 else dp_steady + rng.uniform(-3.0, 3.0)
        particles = float(np.expm1(rng.uniform(0.0, np.log1p(900.0))))
        state = plant.state | {"dp": measured_dp, "particle_count": particles, "particles_05": particles * 0.12}
        disturbance = Disturbance(exhaust, 35.0, source, door_fraction=door)
        prediction = plant.predict(u_mau, u_ffu, state, disturbance, PERIOD_S)
        target = simulated_target(plant, state, prediction, disturbance, u_mau, u_ffu)
        yield state, prediction, disturbance, u_ffu, target


def measured_samples(plant, path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(CSV_FIELDS) <= set(reader.fieldnames or ()):
            raise ValueError("CSV requires these columns: " + ", ".join(CSV_FIELDS))
        for index, row in enumerate(reader, start=2):
            try:
                fields = [float(row[key]) for key in CSV_FIELDS]
                dt = float(row.get("dt_sec", PERIOD_S))
                u_mau, u_ffu, exhaust, door, source, dp, p01, p05, next_dp, next_p01, next_p05 = fields
                if (not np.isfinite(fields).all() or dt != PERIOD_S or not 0 <= min(u_mau, u_ffu, door)
                        or max(u_mau, u_ffu, door) > 1 or min(exhaust, source) < 0
                        or not (0 <= p05 <= p01 and 0 <= next_p05 <= next_p01)):
                    raise ValueError("values outside domain or unexpected sample period")
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid measurement CSV row {index}: {error}") from error
            disturbance = Disturbance(exhaust / 3600.0, 35.0, source, door_fraction=door)
            state = plant.state | {"dp": dp, "particle_count": p01, "particles_05": p05}
            prediction = plant.predict(u_mau, u_ffu, state, disturbance, PERIOD_S)
            yield state, prediction, disturbance, u_ffu, np.array([next_dp, next_p01, next_p05])


def regression_data(samples):
    pressure, particles, errors = [], [], []
    for state, baseline, disturbance, ffu, target in samples:
        pressure.append(pressure_features(state, baseline, disturbance, ffu))
        particles.append(particle_features(state, baseline, disturbance, ffu))
        nominal = np.array([baseline[key] for key in PRESSURE_KEYS + PARTICLE_KEYS])
        errors.append(np.r_[target[0] - nominal[0], np.log1p(target[1:]) - np.log1p(nominal[1:])])
    residuals = np.array(errors)
    return (np.array(pressure), residuals[:, :1]), (np.array(particles), residuals[:, 1:])


def train_gp(train, calibration, evaluation, feature_floor, output_floor):
    x, y = train
    chosen = np.linspace(0, len(x) - 1, min(len(x), MAX_TRAINING_ROWS), dtype=int)
    record = {
        "features": x[chosen].tolist(),
        "residuals": y[chosen].tolist(),
        "center": np.median(x, axis=0).tolist(),
        "scale": np.maximum(1.7 * np.std(x, axis=0), feature_floor).tolist(),
        "output_scale": np.maximum(np.std(y, axis=0), output_floor).tolist(),
        "interval_multiplier": [1.0] * y.shape[1],
        "noise": 0.035,
    }
    gp = ResidualGP(record, x.shape[1], y.shape[1])
    x_cal, y_cal = calibration
    mean, deviation, support = gp.predict(x_cal)
    usable = support >= 0.35
    if usable.sum() < 15:
        raise ValueError("Calibration requires at least 15 transitions within training support")
    error = abs(y_cal[usable] - mean[usable]) / deviation[usable]
    multiplier = np.maximum(1.0, np.quantile(error, 0.95, axis=0, method="higher"))
    record["interval_multiplier"] = multiplier.tolist()

    x_test, y_test = evaluation
    mean, deviation, support = gp.predict(x_test)
    usable = support >= 0.35
    effective = np.where(usable[:, None], mean, 0.0)
    evaluation_record = {
        "physics_mae": np.mean(abs(y_test), axis=0).tolist(),
        "gpr_with_fallback_mae": np.mean(abs(y_test - effective), axis=0).tolist(),
        "empirical_interval_coverage_in_domain": [
            float(value) for value in np.mean(abs(y_test[usable] - mean[usable]) <= multiplier * deviation[usable], axis=0)
        ] if usable.any() else None,
        "gpr_rows": int(usable.sum()), "test_rows": len(x_test),
    }
    return record, evaluation_record


def main(data_path=None):
    plant = CleanroomPlant()
    if data_path is None:
        partitions = [list(synthetic_samples(plant, count, SEED + i)) for i, count in enumerate((192, 240, 360))]
        source = "synthetic_alternate_pressure_and_filtration"
    else:
        samples = list(measured_samples(plant, data_path))
        if len(samples) < 90:
            raise ValueError("At least 90 measured transitions are required for chronological train/calibration/test splits")
        first, second = int(0.60 * len(samples)), int(0.80 * len(samples))
        partitions = [samples[:first], samples[first:second], samples[second:]]
        source = "measured_csv"
    train, calibration, evaluation = map(regression_data, partitions)
    pressure, pressure_metrics = train_gp(train[0], calibration[0], evaluation[0], [3.0, 3.0, 0.30], [0.08])
    particles, particle_metrics = train_gp(
        train[1], calibration[1], evaluation[1], [0.9, 0.9, 1.2, 0.20, 0.30], [0.015, 0.015],
    )
    checkpoint = {
        "model_version": MODEL_VERSION, "model_signature": model_signature(), "training_source": source,
        "partition_sizes": [len(part) for part in partitions],
        "pressure": pressure, "particles": particles,
        "held_out_one_step": {"pressure_pa": pressure_metrics, "particles_log1p": particle_metrics},
    }
    write_json(MODEL_PATH, checkpoint)
    print(f"Saved {MODEL_PATH.name} ({source})")
    print(checkpoint["held_out_one_step"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Chronologically ordered CSV of measured one-step transitions")
    args = parser.parse_args()
    try:
        main(args.data)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Training failed: {error}\n")
