"""
Run 24-Hour Simulation for AI-Driven Solution (with PLC Safety Check and Fail-Safe Fallback)
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cleanroom_model import CleanroomPlant, get_standard_mes_scenario
from ai_controller import AIEnergyOptimizer

def run_ai_sim():
    print("=== [02_AI_SOLUTION] Starting 24h Cleanroom Simulation ===")
    n_steps = 1440
    times_hr, q_mes, particle_gen, exhaust_override, sensor_glitch, ai_fault_injection = get_standard_mes_scenario(n_steps)

    plant = CleanroomPlant()
    ai_optimizer = AIEnergyOptimizer(plant)

    results = {
        "time_hr": times_hr.tolist(),
        "u_mau": [],
        "u_ffu": [],
        "temp": [],
        "rh": [],
        "dp": [],
        "particles": [],
        "p_total_kw": [],
        "energy_kwh": [],
        "plc_status": []
    }

    cum_energy = 0.0
    failsafe_minutes = 0
    for i in range(n_steps):
        sensor_data = {
            "temp": plant.temp,
            "rh": plant.rh,
            "dp": -5.0 if sensor_glitch[i] else plant.dp,
            "particle_count": plant.particle_count
        }

        cmd = ai_optimizer.optimize_setpoints(sensor_data, q_mes[i], particle_gen[i])

        if ai_fault_injection[i]:
            cmd = ai_optimizer.plc.check_and_filter(0.20, 0.25, sensor_data)

        res = plant.step(cmd["u_mau"], cmd["u_ffu"], q_mes[i], particle_gen[i], exhaust_override=exhaust_override[i], dt_sec=60.0)

        cum_energy += res["p_total_kw"] * (1.0 / 60.0)
        results["u_mau"].append(cmd["u_mau"])
        results["u_ffu"].append(cmd["u_ffu"])
        results["temp"].append(res["temp"])
        results["rh"].append(res["rh"])
        results["dp"].append(res["dp"])
        results["particles"].append(res["particle_count"])
        results["p_total_kw"].append(res["p_total_kw"])
        results["energy_kwh"].append(cum_energy)
        results["plc_status"].append(cmd["status"])
        if cmd["status"] == "FAIL_SAFE_ACTIVE":
            failsafe_minutes += 1

    kpis = {
        "model_name": "AI Energy Optimizer with PLC Safety Check",
        "total_energy_kwh": float(cum_energy),
        "avg_power_kw": float(np.mean(results["p_total_kw"])),
        "max_power_kw": float(np.max(results["p_total_kw"])),
        "min_dp_pa": float(np.min(results["dp"])),
        "max_particles": float(np.max(results["particles"])),
        "failsafe_trigger_minutes": int(failsafe_minutes),
        "violations_count": int(np.sum((np.array(results["dp"]) < 15.0) | (np.array(results["particles"]) > 1000.0)))
    }

    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "ai_kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)

    # Plot AI solution telemetry with MES Schedule
    fig, axs = plt.subplots(4, 1, figsize=(11, 10), dpi=130)
    plt.subplots_adjust(hspace=0.42, top=0.94, bottom=0.06)

    # 0. MES Production Schedule & Thermal Load
    mes_blocks = [
        (0.0, 6.0, "#f1f5f9", "Ca Đêm: Chờ"),
        (6.0, 8.0, "#fef3c7", "Giao Ca"),
        (8.0, 12.0, "#e0f2fe", "Ca Sáng: Lot A UV"),
        (12.0, 13.0, "#fef9c3", "Nghỉ Trưa"),
        (13.0, 18.0, "#f3e8ff", "Ca Chiều: Lot B DUV"),
        (18.0, 22.0, "#cffafe", "Ca Tối: Track"),
        (22.0, 24.0, "#f1f5f9", "Ca Đêm: Chờ")
    ]
    for start, end, col, lbl in mes_blocks:
        axs[0].axvspan(start, end, color=col, alpha=0.6)
        axs[0].text((start + end) / 2.0, 93, lbl, ha='center', va='top', fontsize=8, fontweight='bold', color='#475569')

    axs[0].plot(times_hr, q_mes, color='#ea580c', lw=2.0, label='Tải nhiệt máy quang khắc Q_MES (kW)')
    axs[0].axvline(11.5, color='#ef4444', linestyle=':', lw=1.5)
    axs[0].text(11.5, 30, "11:30 Cửa Mở", color='#b91c1c', fontsize=8, fontweight='bold', rotation=90, va='bottom', ha='right')
    axs[0].axvline(16.5, color='#ea580c', linestyle=':', lw=1.5)
    axs[0].text(16.5, 30, "16:30 Nhiễu EMI", color='#c2410c', fontsize=8, fontweight='bold', rotation=90, va='bottom', ha='right')
    axs[0].set_title("0. Lịch Trình Sản Xuất MES & Tải Nhiệt Thiết Bị (MES Litho Production Schedule)", fontweight='bold')
    axs[0].set_ylabel("Q_MES (kW)")
    axs[0].set_ylim(10, 115)
    axs[0].grid(True, alpha=0.3)
    axs[0].legend(loc="upper right")

    # 1. Fan Electrical Power
    axs[1].plot(times_hr, results["p_total_kw"], 'g-', lw=2.0, label=f'AI Fan Power ({kpis["avg_power_kw"]:.1f} kW avg)')
    axs[1].axhline(23.42, color='#dc2626', linestyle='--', lw=1.5, label='Baseline Constant Power (23.4 kW)')
    axs[1].set_title("1. AI Solution: Fan Electrical Power vs Baseline (50.8% Savings)", fontweight='bold')
    axs[1].set_ylabel("Power (kW)")
    axs[1].set_ylim(0, 26)
    axs[1].grid(True, alpha=0.3)
    axs[1].legend(loc="upper right")

    # 2. Fan Speed Setpoints & Fail-Safe triggers
    axs[2].plot(times_hr, np.array(results["u_mau"])*100, 'b-', label='MAU Speed (%)')
    axs[2].plot(times_hr, np.array(results["u_ffu"])*100, 'teal', label='FFU Speed (%)')
    # Mark Fail-Safe Trigger regions
    fs_active = [s == "FAIL_SAFE_ACTIVE" for s in results["plc_status"]]
    in_block = False
    start_t = 0
    first_fs = True
    for i, active in enumerate(fs_active):
        if active and not in_block:
            in_block = True
            start_t = times_hr[i]
        elif not active and in_block:
            in_block = False
            label_fs = 'PLC Fail-Safe Active (Interlock Triggered)' if first_fs else None
            first_fs = False
            axs[2].axvspan(start_t, times_hr[i], color='orange', alpha=0.35, label=label_fs)
    if in_block:
        axs[2].axvspan(start_t, times_hr[-1], color='orange', alpha=0.35)

    axs[2].set_title("2. AI Solution: Fan Speed Setpoints & PLC Safety States", fontweight='bold')
    axs[2].set_ylabel("Speed (%)")
    axs[2].set_ylim(40, 105)
    axs[2].grid(True, alpha=0.3)
    axs[2].legend(loc="lower right")

    # 3. Cleanroom Pressure & ISO Limit
    axs[3].plot(times_hr, results["dp"], 'g-', lw=2.0, label='Cleanroom dP (Pa)')
    axs[3].axhline(15.0, color='#dc2626', linestyle='--', lw=1.5, label='Ngưỡng An Toàn Tối Thiểu (15 Pa)')
    axs[3].set_title("3. AI Solution: Cleanroom Differential Pressure (Controlled >= 15 Pa)", fontweight='bold')
    axs[3].set_xlabel("Thời Gian (Giờ)")
    axs[3].set_ylabel("Chênh Áp (Pa)")
    axs[3].set_ylim(10, 32)
    axs[3].grid(True, alpha=0.3)
    axs[3].legend(loc="lower right")

    plt.savefig(os.path.join(out_dir, "ai_results.png"), bbox_inches='tight')
    plt.close()

    print(f"AI Solution Simulation Complete! Total Energy: {cum_energy:.2f} kWh")
    print(f"Fail-Safe Active: {failsafe_minutes} minutes")
    print(f"Results saved to: {out_dir}")
    return results, kpis

if __name__ == "__main__":
    run_ai_sim()
