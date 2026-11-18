"""Direct two-setpoint policy learned from Bay 1's physics MPC."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from bay1_control import PLCSafetyChecker, bounded, is_finite_number, pressure_minimum_command
from bay1_model import CONFIG, CONTROL, LIMITS, environment_violations


MODEL_VERSION = "bay1-fan-policy-1"
MODEL_PATH = Path(__file__).resolve().parent / "02_ai_solution" / "fan_policy.json"
TRAINING_SOURCE = "synthetic_physics_mpc_imitation"
PERIOD_S = CONTROL["control_period_s"]
SENSOR_FEATURES = ("dp", "particle_count", "particles_05", "temp", "rh", "amc_nh3", "mau_filter_dp")
FEATURE_NAMES = (
    *SENSOR_FEATURES, "mes_load_kw", "particle_source", "current_exhaust", "door_fraction",
    "outdoor_temp", "outdoor_rh", "amc_multiplier", "prev_mau", "prev_ffu", "mau_floor",
    *(f"exhaust_step_{offset}" for offset in range(1, CONTROL["prediction_steps"])),
    *(f"mes_load_step_{offset}" for offset in range(1, CONTROL["prediction_steps"])),
)


def policy_signature():
    return hashlib.sha256(json.dumps([CONFIG, FEATURE_NAMES], sort_keys=True).encode("utf-8")).hexdigest()


def upcoming_requirements(plant, disturbance, forecast, dt_sec):
    upcoming = (disturbance, *forecast[:CONTROL["prediction_steps"] - 1])
    upcoming += (upcoming[-1],) * (CONTROL["prediction_steps"] - len(upcoming))
    slew = CONTROL["max_change_per_minute"] * dt_sec / 60.0
    required = max(pressure_minimum_command(plant, item) - offset * slew for offset, item in enumerate(upcoming))
    return upcoming, required


def policy_inputs(plc, sensors, disturbance, upcoming, requested_floor, dt_sec):
    (lo_mau, hi_mau), (lo_ffu, hi_ffu) = plc.reachable_bounds(dt_sec)
    lower = np.array([bounded(requested_floor, lo_mau, hi_mau), lo_ffu])
    upper = np.array([hi_mau, hi_ffu])
    features = np.array([
        *(sensors[key] for key in SENSOR_FEATURES), disturbance.equipment_kw, disturbance.particles_per_min,
        disturbance.exhaust_m3_s, disturbance.door_fraction, disturbance.outdoor_temp_c, disturbance.outdoor_rh_pct,
        disturbance.amc_multiplier, plc.prev_u_mau, plc.prev_u_ffu, lower[0],
        *(item.exhaust_m3_s for item in upcoming[1:]), *(item.equipment_kw for item in upcoming[1:]),
    ])
    return features, lower, upper


class FanPolicy:
    """Shallow regression tree exported from the offline fit."""

    def __init__(self, tree):
        self.nodes = tree
        if not isinstance(tree, list) or not 1 <= len(tree) <= 512:
            raise ValueError("invalid policy tree")
        reached = {0}
        for index, node in enumerate(tree):
            if index not in reached or len(node) != 4:
                raise ValueError("invalid policy node")
            feature, threshold, left, right = node
            if not all(is_finite_number(value) for value in node) or any(
                not isinstance(value, int) for value in (feature, left, right)
            ):
                raise ValueError("invalid policy node values")
            if feature == -1 and left == right == -1 and 0 <= threshold <= 1:
                continue
            if not (0 <= feature < len(FEATURE_NAMES) and index < left < right < len(tree)):
                raise ValueError("invalid policy edges")
            reached.update((left, right))

    def predict(self, features):
        index = 0
        while index >= 0:
            feature, threshold, left, right = self.nodes[index]
            if feature == -1:
                return threshold
            index = left if features[feature] <= threshold else right


@lru_cache(maxsize=1)
def load_policy():
    record = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if record["model_version"] != MODEL_VERSION or record["policy_signature"] != policy_signature():
        raise ValueError("policy checkpoint does not match Bay 1")
    return FanPolicy(record["mau_tree"]), FanPolicy(record["ffu_tree"])


class DirectFanController:
    """Infer one proposed MAU/FFU pair and submit it to the simulated PLC."""

    def __init__(self, plant):
        self.plc = PLCSafetyChecker(plant)
        self.plant = plant
        try:
            self.policy = load_policy()
        except (OSError, ValueError, TypeError, KeyError):
            self.policy = None

    def command_setpoints(self, sensors, q_mes_kw, particle_gen_rate, network_connected=True, *,
                          now_s, dt_sec=PERIOD_S, forecast=()):
        if not is_finite_number(now_s):
            raise ValueError("now_s must be a finite PLC clock value")
        sensor_ok, _ = self.plc.validate_sensors(sensors)
        load_ok = all(is_finite_number(value) and value >= 0.0 for value in (q_mes_kw, particle_gen_rate))
        disturbance = self.plc.disturbance_from_sensors(sensors, q_mes_kw, particle_gen_rate) if sensor_ok and load_ok else None
        command = (None, None)
        reason = None
        fallback_floor = None
        if not load_ok:
            reason = "Tải MES hoặc nguồn hạt không hợp lệ"
        elif self.policy is None:
            reason = "Thiếu mô hình AI phát lệnh"
        elif dt_sec != PERIOD_S:
            reason = "Chu kỳ khác chu kỳ huấn luyện của AI"
        elif disturbance is not None and network_connected:
            max_pressure = self.plant.compute_pressure_steady(
                self.plant.mau_max_airflow, disturbance.exhaust_m3_s, disturbance.door_fraction,
            )
            if max_pressure < LIMITS["dp_min"]:
                reason = "MAU tối đa không đủ giữ chênh áp tối thiểu"
            else:
                upcoming, fallback_floor = upcoming_requirements(self.plant, disturbance, forecast, dt_sec)
                if not environment_violations(sensors):
                    features, low, high = policy_inputs(self.plc, sensors, disturbance, upcoming, fallback_floor, dt_sec)
                    increments = np.array([model.predict(features) for model in self.policy])
                    command = tuple((low + np.clip(increments, 0.0, 1.0) * (high - low)).tolist())
        timing = {"now_s": now_s, "command_time_s": now_s if command[0] is not None else None}
        fallback = {} if fallback_floor is None else {"fallback_mau_floor": fallback_floor}
        result = self.plc.check_and_filter(
            *command, sensors, network_connected, disturbance=disturbance, dt_sec=dt_sec,
            optimizer_reason=reason, **timing, **fallback,
        )
        return result | {
            "requested_u_mau": command[0], "requested_u_ffu": command[1],
            "ai_inferences": int(command[0] is not None),
            "ai_command_rejected": command[0] is not None and result["status"] == "FAIL_SAFE_ACTIVE",
        }
