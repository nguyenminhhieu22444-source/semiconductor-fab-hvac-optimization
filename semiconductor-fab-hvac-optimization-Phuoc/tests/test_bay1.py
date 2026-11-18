import math
from dataclasses import replace

import numpy as np
import pytest

from bay1_control import AIEnergyOptimizer, FFU_MIN, MAU_MIN, PLCSafetyChecker
from bay1_air_pinn import AirQualityPINN
from bay1_model import CONTROL, LIMITS, CleanroomPlant, Disturbance, dewpoint, humidity_ratio, supply_conditions, well_mixed
from bay1_policy import DirectFanController, MODEL_VERSION as POLICY_VERSION
from bay1_scenarios import generate_benchmark_day, get_all_scenarios
from bay1_simulation import run_scenario_comparison, simulate_single_mode, simulation_step


def test_physics_units_and_fan_table():
    plant = CleanroomPlant()
    assert plant.volume == pytest.approx(2818.8)
    assert plant.compute_pressure_steady(2.0, 2.0) == 0
    assert plant.compute_pressure_steady(2.0, 2.1) < 0
    assert plant.compute_pressure_steady(3.0, 3.0, door_fraction=1.0) == 0
    assert well_mixed(0.0, 480 / 60, 0.0, plant.volume, 60.0) == pytest.approx(480 / plant.volume)
    assert plant.compute_fan_powers(1, FFU_MIN)[1] / plant.n_ffu == pytest.approx(82.7)
    assert dewpoint(humidity_ratio(38.5, 90.0)) == pytest.approx(36.56, abs=0.02)
    normal = supply_conditions(0.95, 29.93, 60.0)
    heat = supply_conditions(0.95, 38.5, 90.0)
    assert heat[1] > normal[1]
    assert sum(heat[2:4]) > sum(normal[2:4])


@pytest.mark.parametrize("sensor_patch", [{"dp": float("nan")}, {"age_s": 300.0}, {"rh": None}, {"particles_05": 200.0}])
def test_gate_filters_bad_inputs_with_slew_limits(sensor_patch):
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, 150.0)
    gate = PLCSafetyChecker(plant)
    gate.prev_u_mau = MAU_MIN
    gate.prev_u_ffu = FFU_MIN
    command = gate.check_and_filter(1.0, 1.0, plant.sensor_data(disturbance) | sensor_patch, disturbance=disturbance, dt_sec=30)
    assert command["production_hold"]
    assert command["status"] == "FAIL_SAFE_ACTIVE"
    assert command["u_mau"] <= MAU_MIN + CONTROL["max_change_per_minute"] / 2
    assert command["u_ffu"] <= FFU_MIN + CONTROL["max_change_per_minute"] / 2
    assert gate.check_and_filter(1.0, 1.0, {}, disturbance=disturbance)["production_hold"]


def test_gate_enforces_environment_and_requires_recovery_samples():
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, 150.0)
    controller = AIEnergyOptimizer(plant)
    sensors = plant.sensor_data(disturbance)
    bad = controller.optimize_setpoints(sensors | {"rh": 95.0}, 35.0, 150.0)
    assert bad["status"] == "FAIL_SAFE_ACTIVE"
    assert bad["production_hold"]
    healthy = [controller.optimize_setpoints(sensors, 35.0, 150.0) for _ in range(CONTROL["recovery_samples"])]
    assert all(command["status"] == "RECOVERING" for command in healthy[:-1])
    assert healthy[-1]["status"] == "SAFE"
    assert not healthy[-1]["production_hold"]
    assert healthy[-1].keys() == bad.keys()


def test_door_infeasibility_is_reported():
    plant = CleanroomPlant()
    d = Disturbance(plant.mau_max_airflow, 90.0, 1100.0, door_fraction=1.0)
    command = AIEnergyOptimizer(plant).optimize_setpoints(plant.sensor_data(d), d.equipment_kw, d.particles_per_min)
    assert command["production_hold"]
    assert any("MAU tối đa" in reason for reason in command["reasons"])
    after = plant.step(command["u_mau"], command["u_ffu"], d.equipment_kw, d.particles_per_min, disturbance=d)
    assert after["dp"] < LIMITS["dp_min"]


def test_gpr_corrects_pressure_and_particles_and_falls_back_outside_domain():
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 90.0, 150.0)
    state = plant.sensor_data(disturbance)
    controller = AIEnergyOptimizer(plant)

    physical = plant.predict(0.95, 0.65, state, disturbance)
    predicted = controller.predict_state(0.95, 0.65, state, 90.0, 150.0)
    assert predicted["prediction_source"] == "gpr"
    for key in ("dp", "particle_count", "particles_05"):
        assert abs(predicted[key] - physical[key]) > 1e-4
        low, high = predicted["prediction_bounds"][key]
        assert low <= predicted[key] <= high
    assert 0 <= predicted["particles_05"] <= predicted["particle_count"]
    for key in ("temp", "rh", "room_coil_kw", "amc_nh3", "p_total_kw"):
        assert predicted[key] == physical[key]

    outside_domain = controller.predict_state(0.95, 0.65, state, 90.0, 150.0, dt_sec=180.0)
    physical_long_step = plant.predict(0.95, 0.65, state, disturbance, dt_sec=180.0)
    assert outside_domain == physical_long_step | {"prediction_source": "physics_fallback"}


def test_mpc_uses_gpr_bounds_and_plc_checks_physical_transition(monkeypatch):
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, 150.0)
    controller = AIEnergyOptimizer(plant)
    sensors = plant.sensor_data(disturbance)
    control = AIEnergyOptimizer(plant, use_gpr=False).optimize_setpoints(sensors, 35.0, 150.0)
    original_predict = controller.gpr.predict_transition
    original_gate = controller.plc.forecast_violations
    checked = []

    def widen_particle_bound(u_mau, u_ffu, *args):
        result = original_predict(u_mau, u_ffu, *args)
        if u_ffu < 0.99:
            result["prediction_bounds"]["particles_05"] = (0.0, LIMITS["particles_05_max"] + 1.0)
        return result

    def record_plc(*args):
        checked.append(args[:2])
        return original_gate(*args)

    monkeypatch.setattr(controller.gpr, "predict_transition", widen_particle_bound)
    monkeypatch.setattr(controller.plc, "forecast_violations", record_plc)
    command = controller.optimize_setpoints(sensors, 35.0, 150.0)
    assert command["status"] == "SAFE"
    assert command["u_ffu"] >= 0.99 > control["u_ffu"]
    assert controller.gpr_evaluations > CONTROL["prediction_steps"]
    assert controller.physics_fallback_evaluations == 0
    assert checked[-1] == (command["u_mau"], command["u_ffu"])


def test_missing_gpr_checkpoint_uses_physics(monkeypatch):
    def missing():
        raise FileNotFoundError("checkpoint unavailable")

    monkeypatch.setattr("bay1_gpr.load_model", missing)
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, 150.0)
    controller = AIEnergyOptimizer(plant)
    command = controller.optimize_setpoints(plant.sensor_data(disturbance), 35.0, 150.0)
    assert command["status"] == "SAFE"
    assert controller.prediction_model == "physics"
    assert controller.gpr_status == "unavailable"
    assert controller.gpr_evaluations == 0
    assert controller.physics_fallback_evaluations >= CONTROL["prediction_steps"]


def test_invalid_control_period_is_rejected_before_forecasting():
    plant = CleanroomPlant()
    sensors = plant.sensor_data(Disturbance(plant.base_exhaust_flow, 35.0, 150.0))
    with pytest.raises(ValueError, match="dt_sec"):
        AIEnergyOptimizer(plant).optimize_setpoints(sensors, 35.0, 150.0, dt_sec=0.0)


def test_ai_sends_one_pair_to_plc_without_running_mpc(monkeypatch):
    def forbid_mpc(*args, **kwargs):
        pytest.fail("AI runtime called MPC")

    monkeypatch.setattr(AIEnergyOptimizer, "optimize_setpoints", forbid_mpc)
    plant = CleanroomPlant()
    controller = DirectFanController(plant)
    original_check = controller.plc.check_and_filter
    submitted = []

    def spy(mau, ffu, *args, **kwargs):
        submitted.append((mau, ffu))
        return original_check(mau, ffu, *args, **kwargs)

    monkeypatch.setattr(controller.plc, "check_and_filter", spy)
    cmd, state = simulation_step(plant, controller, generate_benchmark_day(), 0, "ai")
    assert cmd["status"] == "SAFE"
    assert cmd["ai_inferences"] == 1
    assert not cmd["ai_command_rejected"]
    assert submitted == [(cmd["requested_u_mau"], cmd["requested_u_ffu"])]
    assert state["p_total_kw"] == pytest.approx(sum(plant.compute_fan_powers(*submitted[0])) / 1000)


def test_plc_rejects_stale_command_and_duplicate_recovery_samples():
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, 150.0)
    gate = PLCSafetyChecker(plant)

    def submit(now, sample, issued):
        sensors = plant.sensor_data(disturbance) | {"sample_time_s": sample}
        return gate.check_and_filter(0.95, 1.0, sensors, disturbance=disturbance, now_s=now, command_time_s=issued)

    old = submit(100, 0, 0)
    assert old["status"] == "FAIL_SAFE_ACTIVE"
    assert any("Lệnh AI quá hạn" in reason for reason in old["reasons"])
    assert submit(101, 101, 101)["status"] == "RECOVERING"
    assert submit(102, 101, 102)["status"] == "FAIL_SAFE_ACTIVE"
    assert submit(103, 103, 103)["status"] == "RECOVERING"
    assert submit(104, 104, 104)["status"] == "RECOVERING"
    assert submit(105, 105, 105)["status"] == "SAFE"


def test_direct_ai_prepares_for_scheduled_exhaust_increase():
    plant = CleanroomPlant()
    actual = Disturbance(5000.0 / 3600.0, 35.0, 150.0)
    sensors = plant.sensor_data(actual) | {"sample_time_s": 0.0}
    planned = replace(actual, exhaust_m3_s=8500.0 / 3600.0)
    immediate, anticipated = DirectFanController(plant), DirectFanController(plant)
    for controller in (immediate, anticipated):
        controller.plc.prev_u_mau = MAU_MIN
    current = immediate.command_setpoints(sensors, 35.0, 150.0, now_s=0.0)
    future = anticipated.command_setpoints(sensors, 35.0, 150.0, now_s=0.0, forecast=(planned,))
    assert current["status"] == future["status"] == "SAFE"
    assert future["u_mau"] > current["u_mau"]
    assert future["u_mau"] == pytest.approx(MAU_MIN + CONTROL["max_change_per_minute"])


def test_absent_policy_runs_plc_fallback(monkeypatch):
    def missing():
        raise FileNotFoundError("policy")

    monkeypatch.setattr("bay1_policy.load_policy", missing)
    plant = CleanroomPlant()
    cmd, _ = simulation_step(plant, DirectFanController(plant), generate_benchmark_day(), 0, "ai")
    assert cmd["status"] == "FAIL_SAFE_ACTIVE"
    assert cmd["ai_inferences"] == 0
    assert cmd["requested_u_mau"] is None


def test_pinn_predicts_air_quality_for_the_issued_command():
    plant = CleanroomPlant()
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, 150.0)
    expected = plant.predict(0.95, 0.8, plant.state, disturbance)
    predicted, flags = AirQualityPINN(plant).forecast(0.95, 0.8, plant.state, disturbance, 60.0)
    assert not flags
    assert predicted["dp"] == pytest.approx(expected["dp"], abs=0.01)
    assert predicted["particle_count"] == pytest.approx(expected["particle_count"], abs=0.05)
    assert predicted["particles_05"] == pytest.approx(expected["particles_05"], abs=0.01)


def test_pinn_flags_proposal_before_plc_applies_fallback():
    plant = CleanroomPlant()
    source = 1_000_000.0
    disturbance = Disturbance(plant.base_exhaust_flow, 35.0, source, amc_multiplier=0.0)
    controller = DirectFanController(plant)
    cmd = controller.command_setpoints(plant.sensor_data(disturbance) | {"sample_time_s": 0.0}, 35.0, source, now_s=0.0)
    assert cmd["ai_inferences"] == 1
    assert cmd["pinn_prediction"]["particles_05"] > LIMITS["particles_05_max"]
    assert cmd["pinn_veto"] and cmd["ai_command_rejected"] and cmd["production_hold"]
    assert cmd["status"] == "FAIL_SAFE_ACTIVE"
    assert any("PINN" in reason for reason in cmd["reasons"])


def test_missing_air_pinn_keeps_independent_plc_check(monkeypatch):
    def missing():
        raise FileNotFoundError("air PINN")

    monkeypatch.setattr("bay1_air_pinn.load_air_pinn", missing)
    plant = CleanroomPlant()
    controller = DirectFanController(plant)
    checked = []
    gate_forecast = controller.plc.forecast_violations

    def spy(*args):
        checked.append(args[:2])
        return gate_forecast(*args)

    monkeypatch.setattr(controller.plc, "forecast_violations", spy)
    cmd, _ = simulation_step(plant, controller, generate_benchmark_day(), 0, "ai")
    assert cmd["pinn_prediction"] is None
    assert cmd["status"] == "SAFE"
    assert checked == [(cmd["u_mau"], cmd["u_ffu"])]


def test_full_day_benchmark_and_scenarios():
    scenarios = get_all_scenarios()
    assert np.count_nonzero(scenarios["2"]["door_fraction"]) == 30
    assert np.count_nonzero(scenarios["4"]["amc_multiplier"] > 1.0) == 150
    for case in (generate_benchmark_day(), *scenarios.values()):
        baseline, ai, summary = run_scenario_comparison(case)
        assert summary["baseline"]["duration_hours"] == 24.0
        assert summary["ai_solution"]["policy_model"] == POLICY_VERSION
        assert summary["ai_solution"]["ai_inferences"] == sum(ai["ai_inferences"]) > 0
        assert summary["ai_solution"]["ai_commands_rejected"] == sum(ai["ai_command_rejected"])
        assert summary["ai_solution"]["pinn_forecasts"] == sum(item is not None for item in ai["pinn_prediction"]) > 0
        assert summary["ai_solution"]["pinn_vetoes"] == sum(ai["pinn_veto"])
        assert summary["ai_without_pinn"]["pinn_forecasts"] == 0
        assert summary["pinn_comparison"]["fan_energy_saved_kwh"] == pytest.approx(
            summary["ai_without_pinn"]["total_energy_kwh"] - summary["ai_solution"]["total_energy_kwh"]
        )
        assert summary["physics_mpc"]["median_safe_command_time_us"] > 0.0
        assert summary["policy_comparison"]["fan_energy_saved_kwh"] == pytest.approx(
            summary["physics_mpc"]["total_energy_kwh"] - summary["ai_solution"]["total_energy_kwh"]
        )
        assert math.isfinite(summary["savings_vs_pressure_reference_pct"])
        assert all(not violated for status, violated in zip(ai["plc_status"], ai["violations"]) if status == "SAFE")
        assert max(abs(delta) for delta in np.diff([CONTROL["baseline_mau"], *ai["u_mau"]])) <= 0.040000001
        assert max(abs(delta) for delta in np.diff([CONTROL["baseline_ffu"], *ai["u_ffu"]])) <= 0.040000001
        assert all(p05 <= p01 for p05, p01 in zip(ai["particles_05"], ai["particle_count"]))
        assert ai["energy_kwh"][-1] == pytest.approx(sum(ai["p_total_kw"]) / 60.0)
        if case["id"] in {"scenario_1", "scenario_5"}:
            assert summary["ai_solution"]["violation_minutes"] == 0.0
        if case["id"] == "scenario_3":
            assert max(ai["rh"]) > LIMITS["rh_max"]
        if case["id"] == "scenario_4":
            assert max(baseline["amc_nh3"]) > 0.2
            assert max(ai["amc_nh3"]) > 0.2


def test_variable_step_is_used_for_energy_and_timestamps():
    trace, kpi = simulate_single_mode(generate_benchmark_day(n_steps=720), "baseline")
    assert trace["time_hr"][-1] == pytest.approx(24.0)
    assert kpi["dt_sec"] == 120.0
    assert kpi["total_energy_kwh"] == pytest.approx(kpi["max_power_kw"] * 24.0)
    assert kpi["violation_minutes"] == kpi["violations_count"] * 2.0
