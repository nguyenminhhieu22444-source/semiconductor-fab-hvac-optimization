"""
Run 24-Hour Simulation for Baseline (Traditional Operation)
"""
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cleanroom_model import CleanroomPlant, get_standard_mes_scenario
from baseline_controller import BaselineController

def run_baseline_sim():
    print("=== [01_BASELINE] Starting 24h Cleanroom Simulation ===")
    n_steps = 1440
    times_hr, q_mes, particle_gen, exhaust_override, _, _ = get_standard_mes_scenario(n_steps)

    plant = CleanroomPlant()
    controller = BaselineController(u_mau=0.95, u_ffu=1.00)

    results = {
        "time_hr": times_hr.tolist(),
        "u_mau": [],
        "u_ffu": [],
        "temp": [],
        "rh": [],
        "dp": [],
        "particles": [],
        "p_total_kw": [],
        "energy_kwh": []
    }

    cum_energy = 0.0
    for i in range(n_steps):
        state = {
            "temp": plant.temp,
            "rh": plant.rh,
            "dp": plant.dp,
            "particle_count": plant.particle_count
        }
        cmd = controller.get_setpoints(state, q_mes[i])
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

    # Calculate KPIs
    kpis = {
        "model_name": "Baseline Traditional Operation",
        "total_energy_kwh": float(cum_energy),
        "avg_power_kw": float(np.mean(results["p_total_kw"])),
        "max_power_kw": float(np.max(results["p_total_kw"])),
        "min_dp_pa": float(np.min(results["dp"])),
        "max_particles": float(np.max(results["particles"])),
        "violations_count": int(np.sum((np.array(results["dp"]) < 15.0) | (np.array(results["particles"]) > 1000.0)))
    }

    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "baseline_kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)

    # Plot baseline telemetry with MES Schedule
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
    axs[1].plot(times_hr, results["p_total_kw"], 'r-', lw=2.0, label=f'Baseline Constant Fan Power ({kpis["avg_power_kw"]:.1f} kW avg)')
    axs[1].axhline(11.53, color='#16a34a', linestyle='--', lw=1.5, label='Mục Tiêu Tiết Kiệm AI (11.5 kW)')
    axs[1].set_title("1. Baseline: Tiêu Thụ Điện Quạt Cố Định 100% (562.1 kWh/ngày)", fontweight='bold')
    axs[1].set_ylabel("Power (kW)")
    axs[1].set_ylim(0, 26)
    axs[1].grid(True, alpha=0.3)
    axs[1].legend(loc="upper right")

    # 2. Fan Speed Setpoints
    axs[2].plot(times_hr, np.array(results["u_mau"])*100, 'b-', label='MAU Speed (95% Cố Định)')
    axs[2].plot(times_hr, np.array(results["u_ffu"])*100, 'teal', label='FFU Speed (100% Cố Định)')
    axs[2].set_title("2. Baseline: Điểm Đặt Quạt Cố Định (Không Thích Ứng MES)", fontweight='bold')
    axs[2].set_ylabel("Speed (%)")
    axs[2].set_ylim(40, 105)
    axs[2].grid(True, alpha=0.3)
    axs[2].legend(loc="lower right")

    # 3. Cleanroom Pressure
    axs[3].plot(times_hr, results["dp"], 'r-', lw=2.0, label='Baseline dP (Pa)')
    axs[3].axhline(15.0, color='#dc2626', linestyle='--', lw=1.5, label='Ngưỡng An Toàn Tối Thiểu (15 Pa)')
    axs[3].set_title("3. Baseline: Chênh Áp Dương Phòng Sạch (Differential Pressure)", fontweight='bold')
    axs[3].set_xlabel("Thời Gian (Giờ)")
    axs[3].set_ylabel("Chênh Áp (Pa)")
    axs[3].set_ylim(10, 32)
    axs[3].grid(True, alpha=0.3)
    axs[3].legend(loc="lower right")

    plt.savefig(os.path.join(out_dir, "baseline_results.png"), bbox_inches='tight')
    plt.close()

    print(f"Baseline Simulation Complete! Total Energy: {cum_energy:.2f} kWh")
    print(f"Results saved to: {out_dir}")
    return results, kpis

if __name__ == "__main__":
    run_baseline_sim()
