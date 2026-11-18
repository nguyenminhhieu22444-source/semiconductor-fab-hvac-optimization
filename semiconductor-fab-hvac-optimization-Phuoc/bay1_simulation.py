"""Single simulation and KPI path shared by the benchmark and dashboards."""

import json
from dataclasses import replace
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from uuid import uuid4

from bay1_control import AIEnergyOptimizer, PLCSafetyChecker, pressure_ramp_plan
from bay1_model import CONFIG, CONTROL, CleanroomPlant, Disturbance, environment_violations
from bay1_policy import MODEL_VERSION, TRAINING_SOURCE, DirectFanController
from bay1_scenarios import generate_benchmark_day, get_all_scenarios


ROOT = Path(__file__).resolve().parent


def disturbance_at(scenario, index):
    return Disturbance(
        float(scenario["exhaust_override"][index]),
        float(scenario["q_mes"][index]),
        float(scenario["particle_gen"][index]),
        float(scenario["outdoor_temp"][index]),
        float(scenario["outdoor_rh"][index]),
        float(scenario["door_fraction"][index]),
        float(scenario["amc_multiplier"][index]),
    )


def scheduled_forecast(scenario, index, actual):
    if actual.door_fraction != 0.0 or abs(actual.exhaust_m3_s - scenario["scheduled_exhaust"][index]) >= 0.1:
        return ()
    next_steps = range(index + 1, min(index + CONTROL["prediction_steps"], len(scenario["times_hr"])))
    return tuple(
        replace(actual, equipment_kw=float(scenario["scheduled_q_mes"][future]),
                exhaust_m3_s=float(scenario["scheduled_exhaust"][future]))
        for future in next_steps
    )


def simulation_step(plant, controller, scenario, index, mode):
    actual = disturbance_at(scenario, index)
    dt_sec = scenario["dt_sec"]
    if mode == "baseline":
        command = {
            "u_mau": CONTROL["baseline_mau"], "u_ffu": CONTROL["baseline_ffu"],
            "status": "NORMAL_BASELINE", "reasons": [], "production_hold": False,
        }
    else:
        now_s = index * dt_sec
        sensors = plant.sensor_data(actual) | {"sample_time_s": now_s}
        if scenario["sensor_glitch"][index]:
            sensors["dp"] = float("nan")
        forecast = scheduled_forecast(scenario, index, actual)
        connected = not bool(scenario["ai_fault_injection"][index])
        started_ns = perf_counter_ns()
        if mode == "reference":
            _, minimum_commands = pressure_ramp_plan(plant, actual, forecast, dt_sec)
            command = controller.check_and_filter(
                min(1.0, max(controller.local_pressure_command(actual), minimum_commands[0])),
                CONTROL["baseline_ffu"], sensors,
                disturbance=actual, dt_sec=dt_sec, fallback_mau_floor=minimum_commands[0],
            )
        elif mode == "ai":
            command = controller.command_setpoints(
                sensors, actual.equipment_kw, actual.particles_per_min, connected,
                now_s=now_s, dt_sec=dt_sec, forecast=forecast,
            )
        else:
            command = controller.optimize_setpoints(
                sensors, actual.equipment_kw, actual.particles_per_min,
                network_connected=connected,
                dt_sec=dt_sec, forecast=forecast,
            )
        command["controller_time_us"] = (perf_counter_ns() - started_ns) / 1000.0
    state = plant.step(
        command["u_mau"], command["u_ffu"], actual.equipment_kw, actual.particles_per_min,
        dt_sec=dt_sec, disturbance=actual,
    )
    return command, state


def simulate_single_mode(scenario, mode="ai"):
    if mode not in {"baseline", "reference", "ai", "physics_mpc"}:
        raise ValueError(f"Unknown simulation mode: {mode}")
    plant = CleanroomPlant()
    controller = None
    if mode == "ai":
        controller = DirectFanController(plant)
    elif mode == "physics_mpc":
        controller = AIEnergyOptimizer(plant, use_gpr=False)
    elif mode == "reference":
        controller = PLCSafetyChecker(plant)

    dt_hr = scenario["dt_sec"] / 3600.0
    count = len(scenario["times_hr"])
    history = {"time_hr": [], "u_mau": [], "u_ffu": [], "plc_status": [], "plc_reason": [],
               "production_hold": [], "violations": [], "energy_kwh": [],
               "requested_u_mau": [], "requested_u_ffu": [],
               "ai_inferences": [], "ai_command_rejected": []}
    timings = []
    fan_energy = hvac_energy = reheat_energy = 0.0
    for index in range(count):
        command, state = simulation_step(plant, controller, scenario, index, mode)
        fan_energy += state["p_total_kw"] * dt_hr
        hvac_energy += state["estimated_hvac_electric_kw"] * dt_hr
        reheat_energy += state["mau_reheat_kw"] * dt_hr
        history["time_hr"].append(float(scenario["times_hr"][index]) + dt_hr)
        for key in ("u_mau", "u_ffu", "production_hold"):
            history[key].append(command[key])
        history["plc_status"].append(command["status"])
        history["plc_reason"].append("; ".join(command["reasons"]))
        history["violations"].append(environment_violations(state))
        history["energy_kwh"].append(fan_energy)
        history["requested_u_mau"].append(command.get("requested_u_mau"))
        history["requested_u_ffu"].append(command.get("requested_u_ffu"))
        history["ai_inferences"].append(command.get("ai_inferences", 0))
        history["ai_command_rejected"].append(command.get("ai_command_rejected", False))
        if command["status"] == "SAFE" and mode in {"ai", "physics_mpc"}:
            timings.append(command["controller_time_us"])
        for key, value in state.items():
            history.setdefault(key, []).append(value)

    hours = count * dt_hr
    violations_count = sum(bool(violations) for violations in history["violations"])
    dt_min = scenario["dt_sec"] / 60.0
    kpis = {
        "mode": mode,
        "config_revision": CONFIG["revision"],
        "duration_hours": hours,
        "dt_sec": scenario["dt_sec"],
        "total_energy_kwh": fan_energy,
        "estimated_hvac_electric_kwh": hvac_energy,
        "avg_power_kw": fan_energy / hours,
        "max_power_kw": max(history["p_total_kw"]),
        "total_reheat_energy_kwh": reheat_energy,
        "avg_reheat_kw": reheat_energy / hours,
        "avg_mau_vfd_hz": sum(history["mau_vfd_hz"]) / count,
        "avg_ffu_speed_pct": 100.0 * sum(history["u_ffu"]) / count,
        "min_dp_pa": min(history["dp"]),
        "max_dp_pa": max(history["dp"]),
        "min_temp_c": min(history["temp"]),
        "max_temp_c": max(history["temp"]),
        "min_rh_pct": min(history["rh"]),
        "max_rh_pct": max(history["rh"]),
        "max_particles": max(history["particle_count"]),
        "max_particles_05": max(history["particles_05"]),
        "max_amc_nh3_ppb": max(history["amc_nh3"]),
        "violations_count": violations_count,
        "violation_minutes": violations_count * dt_min,
        "violations_minutes_by_sensor": {
            key: sum(key in row for row in history["violations"]) * dt_min
            for key in ("dp", "temp", "rh", "particle_count", "particles_05", "amc_nh3")
        },
        "failsafe_trigger_minutes": history["plc_status"].count("FAIL_SAFE_ACTIVE") * dt_min,
        "production_hold_minutes": sum(history["production_hold"]) * dt_min,
    }
    if mode in {"ai", "physics_mpc"}:
        kpis["median_safe_command_time_us"] = median(timings) if timings else None
    if mode == "ai":
        kpis["policy_model"] = MODEL_VERSION if controller.policy is not None else None
        kpis["training_source"] = TRAINING_SOURCE if controller.policy is not None else None
        kpis["ai_inferences"] = sum(history["ai_inferences"])
        kpis["ai_commands_rejected"] = sum(history["ai_command_rejected"])
    return history, kpis


def run_scenario_comparison(scenario_data):
    baseline, base_kpis = simulate_single_mode(scenario_data, "baseline")
    _, reference_kpis = simulate_single_mode(scenario_data, "reference")
    physics, physics_kpis = simulate_single_mode(scenario_data, "physics_mpc")
    ai, ai_kpis = simulate_single_mode(scenario_data, "ai")
    base_energy = base_kpis["total_energy_kwh"]
    saved = base_energy - ai_kpis["total_energy_kwh"]
    reference_energy = reference_kpis["total_energy_kwh"]
    reheat_base = base_kpis["total_reheat_energy_kwh"]
    reheat_saved = reheat_base - ai_kpis["total_reheat_energy_kwh"]
    summary = {
        "scenario_id": scenario_data["id"], "scenario_name": scenario_data["name"],
        "scenario_description": scenario_data["description"], "config_revision": CONFIG["revision"],
        "baseline": base_kpis, "pressure_reference": reference_kpis,
        "physics_mpc": physics_kpis, "ai_solution": ai_kpis,
        "policy_comparison": {
            "changed_command_steps": sum(
                abs(ma - mp) > 1e-9 or abs(fa - fp) > 1e-9
                for ma, mp, fa, fp in zip(ai["u_mau"], physics["u_mau"], ai["u_ffu"], physics["u_ffu"])
            ),
            "fan_energy_saved_kwh": physics_kpis["total_energy_kwh"] - ai_kpis["total_energy_kwh"],
            "additional_violation_minutes": ai_kpis["violation_minutes"] - physics_kpis["violation_minutes"],
        },
        "savings_kwh": saved, "savings_pct": 100.0 * saved / base_energy,
        "savings_vs_pressure_reference_pct": 100.0 * (reference_energy - ai_kpis["total_energy_kwh"]) / reference_energy,
        "reheat_saved_kwh": reheat_saved,
        "reheat_saved_pct": 100.0 * reheat_saved / reheat_base if reheat_base else None,
    }
    return baseline, ai, summary


def write_output(path, contents):
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp.write_text(contents, encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def write_json(path, data):
    write_output(path, json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n")


def export_standard_benchmark():
    scenario = generate_benchmark_day()
    baseline, ai, summary = run_scenario_comparison(scenario)
    write_json(ROOT / "benchmark_comparison.json", summary)
    write_json(ROOT / "01_baseline" / "baseline_kpis.json", summary["baseline"])
    write_json(ROOT / "02_ai_solution" / "ai_kpis.json", summary["ai_solution"])
    # A script asset can be read directly from disk by the offline dashboard.
    context = [
        {
            "t": float(scenario["times_hr"][i]),
            "q_mes": float(scenario["q_mes"][i]),
            "particle_gen": float(scenario["particle_gen"][i]),
            "exhaust_flow": float(scenario["exhaust_override"][i]),
            "door_disturbance": bool(scenario["door_fraction"][i]),
            "sensor_glitch": bool(scenario["sensor_glitch"][i]),
            "ai_fault": bool(scenario["ai_fault_injection"][i]),
        }
        for i in range(len(scenario["times_hr"]))
    ]
    data = {"config": CONFIG, "scenario": context, "baseline": baseline, "ai": ai, "summary": summary}
    write_output(ROOT / "bay1_traces.js", "window.BAY1_TRACES = " + json.dumps(
        data, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ) + ";\n")
    return baseline, ai, summary


def run_all_scenarios_and_export():
    results = {}
    for key, scenario in get_all_scenarios().items():
        _, _, result = run_scenario_comparison(scenario)
        results[key] = result
        print(
            f"{key}. {scenario['name']} - điện quạt giảm {result['savings_pct']:.2f}%, "
            f"vi phạm baseline/AI {result['baseline']['violation_minutes']:.0f}/{result['ai_solution']['violation_minutes']:.0f} phút"
        )
    write_json(ROOT / "03_scenario_testing" / "scenarios_benchmark_results.json", results)
    return results
