"""Receding-horizon fan control and independent simulated interlock."""

import math
from itertools import product
from numbers import Real

from bay1_model import CONTROL, FFU, LIMITS, MAU, CleanroomPlant, Disturbance, environment_violations, leakage_flow
from bay1_gpr import MODEL_VERSION, CleanroomGPR


def bounded(value, low, high):
    return min(high, max(low, value))


MAU_MIN = MAU["min_command"]
FFU_MIN = FFU["min_face_velocity_m_s"] / FFU["rated_face_velocity_m_s"]
FORECAST_LIMITS = {
    "dp": (LIMITS["dp_min"], LIMITS["dp_max"]),
    "particle_count": (0.0, LIMITS["particles_01_max"]),
    "particles_05": (0.0, LIMITS["particles_05_max"]),
}


def is_finite_number(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def pressure_minimum_command(plant, disturbance):
    required_flow = disturbance.exhaust_m3_s + leakage_flow(
        CONTROL["planning_dp_floor_pa"], disturbance.door_fraction,
    )
    return max(MAU_MIN, required_flow / plant.mau_max_airflow)


def pressure_ramp_plan(plant, disturbance, forecast, dt_sec):
    """Back-propagate future flow requirements through the MAU slew limit."""
    horizon = (disturbance, *forecast[:CONTROL["prediction_steps"] - 1])
    horizon += (horizon[-1],) * (CONTROL["prediction_steps"] - len(horizon))
    change = CONTROL["max_change_per_minute"] * dt_sec / 60.0
    minimum_commands = [pressure_minimum_command(plant, item) for item in horizon]
    for index in range(len(minimum_commands) - 2, -1, -1):
        minimum_commands[index] = max(minimum_commands[index], minimum_commands[index + 1] - change)
    return horizon, minimum_commands


class PLCSafetyChecker:
    """Simulated interlock. A hold flag represents a request to inhibit production."""

    sensor_ranges = {
        "temp": (-10.0, 60.0),
        "rh": (0.0, 100.0),
        "dp": (-150.0, 150.0),
        "particle_count": (0.0, 1_000_000.0),
        "particles_05": (0.0, 1_000_000.0),
        "amc_nh3": (0.0, 1_000.0),
        "room_coil_kw": (0.0, 1_000.0),
        "exhaust_flow": (0.0, 6.0),
        "door_fraction": (0.0, 1.0),
        "outdoor_temp": (-40.0, 60.0),
        "outdoor_rh": (0.0, 100.0),
        "amc_multiplier": (0.0, 100.0),
        "mau_filter_dp": (0.0, MAU["filter_dp_alarm_pa"]),
        "age_s": (0.0, CONTROL["sensor_max_age_s"]),
    }

    def __init__(self, plant_model=None):
        self.plant = plant_model if plant_model is not None else CleanroomPlant()
        self.prev_u_mau = CONTROL["baseline_mau"]
        self.prev_u_ffu = CONTROL["baseline_ffu"]
        self.failsafe_active = False
        self.reasons = []
        self.last_valid_disturbance = None
        self.good_samples = 0
        self.last_sample_time_s = None
        self.last_command_time_s = None

    def validate_sensors(self, sensor_data):
        for key, (low, high) in self.sensor_ranges.items():
            value = sensor_data.get(key)
            if not is_finite_number(value):
                return False, f"Tín hiệu thiếu hoặc không hữu hạn: {key}"
            if not low <= value <= high:
                return False, f"Tín hiệu ngoài miền hợp lệ: {key}"
        if sensor_data["particles_05"] > sensor_data["particle_count"]:
            return False, "Kênh hạt ≥0,5 µm lớn hơn kênh ≥0,1 µm"
        return True, ""

    @staticmethod
    def disturbance_from_sensors(sensor_data, q_mes_kw, particle_gen_rate):
        return Disturbance(
            sensor_data["exhaust_flow"], q_mes_kw, particle_gen_rate,
            sensor_data["outdoor_temp"], sensor_data["outdoor_rh"],
            sensor_data["door_fraction"], sensor_data["amc_multiplier"],
        )

    def reachable_bounds(self, dt_sec):
        if not is_finite_number(dt_sec) or dt_sec <= 0.0:
            raise ValueError("dt_sec must be finite and positive")
        change = CONTROL["max_change_per_minute"] * dt_sec / 60.0
        return (
            (max(MAU_MIN, self.prev_u_mau - change), min(1.0, self.prev_u_mau + change)),
            (max(FFU_MIN, self.prev_u_ffu - change), min(1.0, self.prev_u_ffu + change)),
        )

    def local_pressure_command(self, disturbance):
        if disturbance is None:
            return CONTROL["baseline_mau"]
        target_flow = disturbance.exhaust_m3_s + leakage_flow(CONTROL["pressure_target_pa"], disturbance.door_fraction)
        return bounded(target_flow / self.plant.mau_max_airflow, MAU_MIN, 1.0)

    def forecast_violations(self, u_mau, u_ffu, sensor_data, disturbance, dt_sec):
        return environment_violations(self.plant.predict(u_mau, u_ffu, sensor_data, disturbance, dt_sec))

    def timestamp_errors(self, now_s, sample_time_s, command_time_s, has_command):
        if not is_finite_number(now_s):
            return ["Thiếu thời gian chu kỳ PLC"]
        reasons = []
        if (is_finite_number(sample_time_s) and 0.0 <= now_s - sample_time_s <= CONTROL["sensor_max_age_s"]
                and (self.last_sample_time_s is None or sample_time_s > self.last_sample_time_s)):
            self.last_sample_time_s = sample_time_s
        else:
            reasons.append("Mẫu cảm biến quá hạn, trùng hoặc sai thứ tự")
        if has_command:
            if (is_finite_number(command_time_s) and is_finite_number(sample_time_s)
                    and sample_time_s <= command_time_s
                    and 0.0 <= now_s - command_time_s <= CONTROL["command_max_age_s"]
                    and (self.last_command_time_s is None or command_time_s > self.last_command_time_s)):
                self.last_command_time_s = command_time_s
            else:
                reasons.append("Lệnh AI quá hạn, trùng hoặc sai thứ tự")
        return reasons

    def check_and_filter(self, candidate_u_mau, candidate_u_ffu, sensor_data, network_connected=True,
                         *, disturbance=None, dt_sec=60.0, optimizer_reason=None, fallback_mau_floor=MAU_MIN,
                         now_s=None, command_time_s=None):
        bounds = self.reachable_bounds(dt_sec)
        sensor_ok, sensor_message = self.validate_sensors(sensor_data)
        timestamp_issues = self.timestamp_errors(
            now_s, sensor_data.get("sample_time_s"), command_time_s,
            candidate_u_mau is not None or candidate_u_ffu is not None,
        ) if now_s is not None else []
        reasons = list(timestamp_issues)
        if not sensor_ok:
            reasons.append(sensor_message)
        elif disturbance is not None and not timestamp_issues:
            self.last_valid_disturbance = disturbance
            for variable in environment_violations(sensor_data):
                reasons.append(f"Đang vi phạm giới hạn: {variable}")
        if not network_connected:
            reasons.append("Mất kết nối nguồn phát lệnh")
        if optimizer_reason:
            reasons.append(optimizer_reason)

        if not reasons:
            if disturbance is None:
                reasons.append("Thiếu dữ liệu để kiểm chứng lệnh")
            elif not all(
                is_finite_number(command) and low <= command <= 1.0
                for command, low in ((candidate_u_mau, MAU_MIN), (candidate_u_ffu, FFU_MIN))
            ):
                reasons.append("Lệnh quạt ngoài giới hạn")
            else:
                actual_mau = bounded(candidate_u_mau, *bounds[0])
                actual_ffu = bounded(candidate_u_ffu, *bounds[1])
                for variable in self.forecast_violations(actual_mau, actual_ffu, sensor_data, disturbance, dt_sec):
                    reasons.append(f"Lệnh thực thi dự báo vi phạm: {variable}")

        if reasons:
            self.failsafe_active = True
            self.good_samples = 0
            fallback_mau = max(self.local_pressure_command(self.last_valid_disturbance), fallback_mau_floor)
            actual_mau = bounded(fallback_mau, *bounds[0])
            actual_ffu = bounds[1][1]
            status = "FAIL_SAFE_ACTIVE"
        elif self.failsafe_active:
            self.good_samples += 1
            self.failsafe_active = self.good_samples < CONTROL["recovery_samples"]
            status = "RECOVERING" if self.failsafe_active else "SAFE"
            if self.failsafe_active:
                reasons.append(f"Xác nhận phục hồi {self.good_samples}/{CONTROL['recovery_samples']}")
        else:
            status = "SAFE"

        self.prev_u_mau = actual_mau
        self.prev_u_ffu = actual_ffu
        self.reasons = reasons
        return {
            "u_mau": actual_mau,
            "u_ffu": actual_ffu,
            "mau_vfd_hz": MAU["rated_hz"] * actual_mau,
            "status": status,
            "reasons": reasons,
            "production_hold": self.failsafe_active,
        }


class AIEnergyOptimizer:
    """Predictive grid search with scheduled MAU ramping and a held FFU action."""

    def __init__(self, plant_model, *, use_gpr=True):
        self.plant = plant_model
        self.plc = PLCSafetyChecker(plant_model)
        self.gpr = CleanroomGPR(plant_model) if use_gpr else None
        self.training_source = self.gpr.training_source if use_gpr else None
        self.prediction_model = MODEL_VERSION if self.training_source else "physics"
        self.gpr_status = "disabled" if not use_gpr else "loaded" if self.training_source else "unavailable"
        self.gpr_evaluations = 0
        self.physics_fallback_evaluations = 0

    def predict_state(self, u_mau, u_ffu, current_state, q_mes_kw, particle_gen_rate, dt_sec=60.0):
        disturbance = self.plc.disturbance_from_sensors(current_state, q_mes_kw, particle_gen_rate)
        return self.predict_transition(u_mau, u_ffu, current_state, disturbance, dt_sec)

    def predict_transition(self, u_mau, u_ffu, state, disturbance, dt_sec):
        if self.gpr is not None:
            return self.gpr.predict_transition(u_mau, u_ffu, state, disturbance, dt_sec)
        prediction = self.plant.predict(u_mau, u_ffu, state, disturbance, dt_sec)
        return prediction | {"prediction_source": "physics"}

    @staticmethod
    def candidate_axis(bounds, target):
        low, high = bounds
        grid = CONTROL["grid_spacing"]
        interior = [index * grid for index in range(math.ceil(low / grid), math.floor(high / grid) + 1)]
        return sorted({low, high, bounded(target, low, high), *interior})

    def optimize_setpoints(self, sensor_data, q_mes_kw, particle_gen_rate, network_connected=True, *,
                           dt_sec=60.0, forecast=()):
        self.gpr_evaluations = 0
        self.physics_fallback_evaluations = 0
        sensor_ok, _ = self.plc.validate_sensors(sensor_data)
        load_ok = all(is_finite_number(value) and value >= 0.0 for value in (q_mes_kw, particle_gen_rate))
        disturbance = self.plc.disturbance_from_sensors(sensor_data, q_mes_kw, particle_gen_rate) if sensor_ok and load_ok else None
        if not sensor_ok or not load_ok or not network_connected:
            return self.plc.check_and_filter(
                None, None, sensor_data, network_connected, disturbance=disturbance, dt_sec=dt_sec,
                optimizer_reason=None if load_ok else "Tải MES hoặc nguồn hạt không hợp lệ",
            )

        max_pressure = self.plant.compute_pressure_steady(self.plant.mau_max_airflow, disturbance.exhaust_m3_s, disturbance.door_fraction)
        if max_pressure < LIMITS["dp_min"]:
            return self.plc.check_and_filter(
                None, None, sensor_data, disturbance=disturbance, dt_sec=dt_sec,
                optimizer_reason="MAU tối đa không đủ giữ chênh áp tối thiểu",
            )

        mau_bounds, ffu_bounds = self.plc.reachable_bounds(dt_sec)
        horizon, minimum_commands = pressure_ramp_plan(self.plant, disturbance, forecast, dt_sec)
        if environment_violations(sensor_data):
            return self.plc.check_and_filter(
                None, None, sensor_data, disturbance=disturbance, dt_sec=dt_sec,
                fallback_mau_floor=minimum_commands[0],
            )
        first_required_mau = min(mau_bounds[1], max(mau_bounds[0], minimum_commands[0]))
        mau_values = self.candidate_axis((first_required_mau, mau_bounds[1]), self.plc.local_pressure_command(disturbance))
        ffu_values = self.candidate_axis(ffu_bounds, FFU_MIN)
        change = CONTROL["max_change_per_minute"] * dt_sec / 60.0
        mau_schedules = {}
        for first_mau in mau_values:
            sequence = [first_mau]
            for required_mau in minimum_commands[1:]:
                previous = sequence[-1]
                sequence.append(min(1.0, bounded(required_mau, previous - change, previous + change)))
            mau_schedules[first_mau] = sequence
        mau_cost = {mau: sum(speed**3 for speed in sequence) * MAU["rated_fan_kw"] * 1000.0
                    for mau, sequence in mau_schedules.items()}
        ffu_cost = {ffu: len(horizon) * self.plant.compute_fan_powers(0.0, ffu)[1] for ffu in ffu_values}
        candidates = sorted(product(mau_values, ffu_values), key=lambda command: mau_cost[command[0]] + ffu_cost[command[1]])
        physics_rejected = False
        for u_mau, u_ffu in candidates:
            state = sensor_data
            for planned_mau, predicted_disturbance in zip(mau_schedules[u_mau], horizon):
                state = self.predict_transition(planned_mau, u_ffu, state, predicted_disturbance, dt_sec)
                if state["prediction_source"] == "gpr":
                    self.gpr_evaluations += 1
                elif state["prediction_source"] == "physics_fallback":
                    self.physics_fallback_evaluations += 1
                intervals = state.get("prediction_bounds", {})
                if environment_violations(state) or any(
                    low < FORECAST_LIMITS[key][0] or high > FORECAST_LIMITS[key][1]
                    for key, (low, high) in intervals.items()
                ):
                    break
            else:
                if self.plc.forecast_violations(u_mau, u_ffu, sensor_data, disturbance, dt_sec):
                    physics_rejected = True
                    continue
                return self.plc.check_and_filter(
                    u_mau, u_ffu, sensor_data, disturbance=disturbance, dt_sec=dt_sec,
                )

        reason = "Không tìm thấy lệnh khả thi trong miền điều khiển dự báo"
        if physics_rejected:
            reason += " và kiểm tra vật lý của chốt"
        return self.plc.check_and_filter(
            None, None, sensor_data, disturbance=disturbance, dt_sec=dt_sec,
            optimizer_reason=reason,
            fallback_mau_floor=minimum_commands[0],
        )
