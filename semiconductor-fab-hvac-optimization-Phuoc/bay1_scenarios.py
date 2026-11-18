"""Common 24-hour MES profiles and reproducible disturbances."""

import numpy as np

from bay1_model import CONFIG, CONTROL

DEFAULT_STEPS = round(86400.0 / CONTROL["control_period_s"])


def generate_scenario_1_standard(n_steps=DEFAULT_STEPS, seed=42):
    if n_steps < 1:
        raise ValueError("n_steps must be positive")
    t = np.linspace(0.0, 24.0, n_steps, endpoint=False)
    rng = np.random.default_rng(seed)
    rated_exhaust = sum(CONFIG["exhaust_m3h"].values())
    shift = np.select(
        [t < 6.0, t < 8.0, t < 12.0, t < 13.0, t < 18.0, t < 22.0],
        [0, 1, 2, 3, 4, 5], default=6,
    )
    ramp = np.clip((t - 6.0) / 2.0, 0.0, 1.0)
    expected_load = np.choose(shift, [25.0, 25.0 + 65.0 * ramp, 90.0, 60.0, 88.0, 50.0, 28.0])
    expected_particles = np.choose(shift, [120.0, 150.0 + 330.0 * ramp, 480.0, 280.0, 470.0, 260.0, 130.0])
    expected_exhaust = np.choose(shift, [5000.0, 5000.0 + (rated_exhaust - 5000.0) * ramp, rated_exhaust, 6500.0, rated_exhaust, 6200.0, 5000.0])
    sun = np.maximum(0.0, np.sin((t - 6.0) * np.pi / 12.0))
    return {
        "id": "scenario_1",
        "name": "Vận hành chuẩn hai ca",
        "description": "Lịch MES tổng hợp với tải nhiệt, nguồn hạt và lưu lượng xả thay đổi theo ca.",
        "times_hr": t,
        "dt_sec": 86400.0 / n_steps,
        "q_mes": np.maximum(0.0, expected_load + rng.normal(0.0, 1.0, n_steps)),
        "particle_gen": np.maximum(0.0, expected_particles + rng.normal(0.0, 15.0, n_steps)),
        "exhaust_override": (expected_exhaust + rng.normal(0.0, 35.0, n_steps)) / 3600.0,
        "scheduled_q_mes": expected_load,
        "scheduled_exhaust": expected_exhaust / 3600.0,
        "outdoor_temp": 28.0 + 4.0 * sun,
        "outdoor_rh": 66.0 - 6.0 * sun,
        "door_fraction": np.zeros(n_steps),
        "amc_multiplier": np.ones(n_steps),
        "sensor_glitch": np.zeros(n_steps, dtype=bool),
        "ai_fault_injection": np.zeros(n_steps, dtype=bool),
    }


def interval(scenario, start_hr, end_hr):
    return (scenario["times_hr"] >= start_hr) & (scenario["times_hr"] < end_hr)


def generate_benchmark_day(n_steps=DEFAULT_STEPS, seed=42):
    data = generate_scenario_1_standard(n_steps, seed)
    data.update(
        id="benchmark",
        name="Đối chuẩn 24 giờ kèm sự cố",
        description="Hai ca, mất kết nối AI, mở cửa đi kèm tăng xả và lỗi cảm biến.",
    )
    door = interval(data, 11.5, 11.75)
    data["door_fraction"][door] = 1.0
    data["exhaust_override"][door] = 10200.0 / 3600.0
    data["particle_gen"][door] += 400.0
    data["ai_fault_injection"] = interval(data, 3.0, 3.25)
    data["sensor_glitch"] = interval(data, 16.5, 16.75)
    return data


def get_standard_mes_scenario(n_steps=DEFAULT_STEPS, seed=42):
    """Legacy MES tuple kept for readers of the earlier cleanroom_model modules."""
    data = generate_benchmark_day(n_steps, seed)
    return tuple(data[key] for key in (
        "times_hr", "q_mes", "particle_gen", "exhaust_override", "sensor_glitch", "ai_fault_injection",
    ))


def generate_scenario_2_door_breach(n_steps=DEFAULT_STEPS, seed=42):
    data = generate_scenario_1_standard(n_steps, seed)
    data.update(
        id="scenario_2", name="Mở cửa và mất kết nối",
        description="Cửa mở 11:30–12:00, xả 10.800 m³/h, tăng nguồn 750 hạt/phút. Mất kết nối 14:00–14:15.",
    )
    door = interval(data, 11.5, 12.0)
    data["door_fraction"][door] = 1.0
    data["exhaust_override"][door] = 10800.0 / 3600.0
    data["particle_gen"][door] += 750.0
    data["ai_fault_injection"] = interval(data, 14.0, 14.25)
    return data


def generate_scenario_3_summer_heatwave(n_steps=DEFAULT_STEPS, seed=42):
    data = generate_scenario_1_standard(n_steps, seed)
    data.update(
        id="scenario_3", name="Sóng nhiệt và tải ẩm cao",
        description="Đỉnh 38,5 °C và 90% RH, tương ứng điểm sương xấp xỉ 36,6 °C.",
    )
    heat = np.maximum(0.0, np.sin((data["times_hr"] - 7.0) * np.pi / 14.0))
    data["outdoor_temp"] = 30.0 + 8.5 * heat
    data["outdoor_rh"] = 75.0 + 15.0 * heat
    return data


def generate_scenario_4_chemical_amc_surge(n_steps=DEFAULT_STEPS, seed=42):
    data = generate_scenario_1_standard(n_steps, seed)
    data.update(
        id="scenario_4", name="Tăng phát thải NH₃ và xả công nghệ",
        description="Nguồn NH₃ nhân 4,5 và lưu lượng xả tăng 1.500 m³/h từ 14:00 đến 16:30.",
    )
    event = interval(data, 14.0, 16.5)
    data["amc_multiplier"][event] = 4.5
    data["exhaust_override"][event] += 1500.0 / 3600.0
    return data


def generate_scenario_5_weekend_maintenance(n_steps=DEFAULT_STEPS, seed=42):
    data = generate_scenario_1_standard(n_steps, seed)
    data.update(
        id="scenario_5", name="Chế độ chờ cuối tuần",
        description="Tải MES khoảng 25 kW, xả 4.800 m³/h và nguồn NH₃ giảm.",
    )
    rng = np.random.default_rng(seed)
    data["q_mes"] = 25.0 + rng.normal(0.0, 1.0, n_steps)
    data["particle_gen"] = np.maximum(0.0, 80.0 + rng.normal(0.0, 15.0, n_steps))
    data["exhaust_override"].fill(4800.0 / 3600.0)
    data["scheduled_q_mes"].fill(25.0)
    data["scheduled_exhaust"].fill(4800.0 / 3600.0)
    data["outdoor_temp"].fill(27.5)
    data["outdoor_rh"].fill(60.0)
    data["amc_multiplier"].fill(0.6)
    return data


def get_all_scenarios(n_steps=DEFAULT_STEPS):
    return {
        str(index): generate(n_steps)
        for index, generate in enumerate((
            generate_scenario_1_standard,
            generate_scenario_2_door_breach,
            generate_scenario_3_summer_heatwave,
            generate_scenario_4_chemical_amc_surge,
            generate_scenario_5_weekend_maintenance,
        ), 1)
    }
