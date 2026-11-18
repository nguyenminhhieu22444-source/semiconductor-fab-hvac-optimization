"""
Interactive Dual-Screen Comparison Visualizer:
Runs 01_Baseline and 02_AI_Solution simultaneously side-by-side in real time!
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Setup module imports
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root_dir, "01_baseline"))
sys.path.append(os.path.join(root_dir, "02_ai_solution"))

from cleanroom_model import CleanroomPlant, get_standard_mes_scenario
from baseline_controller import BaselineController
from ai_controller import AIEnergyOptimizer

def run_interactive_comparison(speed_factor=10):
    print("=" * 75)
    print("  LAUNCHING DUAL INTERACTIVE BENCHMARK: BASELINE vs AI SOLUTION")
    print("=" * 75)
    print(f"-> Speed Factor: {speed_factor} sim-minutes per frame")
    print("-> Close the window or press Ctrl+C in terminal to stop.\n")

    n_steps = 1440
    times_hr, q_mes, particle_gen, exhaust_override, sensor_glitch, ai_fault = get_standard_mes_scenario(n_steps)

    # Initialize Plants
    plant_base = CleanroomPlant()
    ctrl_base = BaselineController(u_mau=0.95, u_ffu=1.00)

    plant_ai = CleanroomPlant()
    ctrl_ai = AIEnergyOptimizer(plant_ai)

    # Trackers
    tracker = {
        "step": 0,
        "energy_base": 0.0,
        "energy_ai": 0.0,
        "time": [],
        "p_base": [],
        "p_ai": [],
        "e_base": [],
        "e_ai": [],
        "dp_base": [],
        "dp_ai": [],
        "part_base": [],
        "part_ai": [],
        "u_mau_ai": [],
        "u_ffu_ai": [],
        "plc_status": []
    }

    # Setup Figure with 2x2 Subplots
    fig, axs = plt.subplots(2, 2, figsize=(14, 8.5))
    fig.canvas.manager.set_window_title("SemiconFab Digital Twin - Real-Time Benchmark Comparison")
    plt.subplots_adjust(hspace=0.35, wspace=0.22, top=0.91, bottom=0.08, left=0.08, right=0.96)

    # Subplot [0, 0]: Instantaneous Fan Power (kW)
    line_p_base, = axs[0, 0].plot([], [], color='#dc2626', linestyle='--', lw=1.8, label="01_Baseline (100% Constant)")
    line_p_ai, = axs[0, 0].plot([], [], color='#16a34a', lw=2.2, label="02_AI Solution (Dynamic)")
    axs[0, 0].set_xlim(0, 24)
    axs[0, 0].set_ylim(0, 26)
    axs[0, 0].set_ylabel("Power (kW)", fontweight='bold')
    axs[0, 0].set_title("1. Instantaneous Fan Electrical Power (kW)", fontweight='bold', fontsize=11)
    axs[0, 0].grid(True, alpha=0.3)
    axs[0, 0].legend(loc="upper right")

    # Subplot [0, 1]: Cumulative Energy & Savings
    line_e_base, = axs[0, 1].plot([], [], color='#dc2626', linestyle='--', lw=1.8, label="Baseline Energy")
    line_e_ai, = axs[0, 1].plot([], [], color='#16a34a', lw=2.2, label="AI Solution Energy")
    axs[0, 1].set_xlim(0, 24)
    axs[0, 1].set_ylim(0, 600)
    axs[0, 1].set_ylabel("Energy (kWh)", fontweight='bold')
    axs[0, 1].set_title("2. Cumulative Electrical Energy Consumption", fontweight='bold', fontsize=11)
    axs[0, 1].grid(True, alpha=0.3)
    axs[0, 1].legend(loc="upper left")

    # Subplot [1, 0]: Differential Pressure (Delta P)
    line_dp_base, = axs[1, 0].plot([], [], color='#ea580c', linestyle='--', lw=1.6, label="Baseline dP")
    line_dp_ai, = axs[1, 0].plot([], [], color='#059669', lw=2.0, label="AI Solution dP")
    axs[1, 0].axhline(15.0, color='black', linestyle='-', lw=1.5, label="ISO Min Limit (15 Pa)")
    axs[1, 0].fill_between([0, 24], 15.0, 32.0, color='#10b981', alpha=0.08)
    axs[1, 0].set_xlim(0, 24)
    axs[1, 0].set_ylim(10, 32)
    axs[1, 0].set_xlabel("Time (Hours)", fontweight='bold')
    axs[1, 0].set_ylabel("Pressure (Pa)", fontweight='bold')
    axs[1, 0].set_title("3. Differential Pressure (Delta P) Comparison", fontweight='bold', fontsize=11)
    axs[1, 0].grid(True, alpha=0.3)
    axs[1, 0].legend(loc="lower right")

    # Subplot [1, 1]: Airborne Particles & ISO Class 3
    line_c_base, = axs[1, 1].plot([], [], color='#9333ea', linestyle='--', lw=1.6, label="Baseline Particles")
    line_c_ai, = axs[1, 1].plot([], [], color='#2563eb', lw=2.0, label="AI Solution Particles")
    axs[1, 1].axhline(1000.0, color='#dc2626', linestyle='--', lw=1.5, label="ISO Class 3 Threshold (1000)")
    axs[1, 1].fill_between([0, 24], 0, 1000.0, color='#3b82f6', alpha=0.06)
    axs[1, 1].set_xlim(0, 24)
    axs[1, 1].set_ylim(0, 1100)
    axs[1, 1].set_xlabel("Time (Hours)", fontweight='bold')
    axs[1, 1].set_ylabel("Particles / m³", fontweight='bold')
    axs[1, 1].set_title("4. Airborne Particle Concentration Comparison", fontweight='bold', fontsize=11)
    axs[1, 1].grid(True, alpha=0.3)
    axs[1, 1].legend(loc="upper right")

    # Top Header Banner Text
    status_text = fig.text(
        0.50, 0.96,
        "Initializing Benchmark Comparison...",
        ha="center", va="center", fontsize=11.5, fontweight='bold',
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8fafc", edgecolor="#0284c7", lw=1.5)
    )

    def update_frame(frame):
        curr = tracker["step"]
        if curr >= n_steps:
            kwh_saved = tracker["energy_base"] - tracker["energy_ai"]
            pct_saved = (kwh_saved / tracker["energy_base"]) * 100.0
            status_text.set_text(
                f"BENCHMARK COMPLETED | Baseline: {tracker['energy_base']:.1f} kWh | AI: {tracker['energy_ai']:.1f} kWh | TIẾT KIỆM: {kwh_saved:.1f} kWh ({pct_saved:.1f}%)"
            )
            status_text.set_backgroundcolor("#dcfce7")
            return line_p_base, line_p_ai, line_e_base, line_e_ai, line_dp_base, line_dp_ai, line_c_base, line_c_ai

        steps_to_run = min(speed_factor, n_steps - curr)
        for _ in range(steps_to_run):
            idx = tracker["step"]
            t_hr = times_hr[idx]

            # 1. Step Baseline
            u_mau_b, u_ffu_b = ctrl_base.get_setpoints()
            res_b = plant_base.step(
                u_mau_b, u_ffu_b, q_mes[idx], particle_gen[idx],
                exhaust_override=exhaust_override[idx], dt_sec=60.0
            )
            tracker["energy_base"] += res_b["p_total_kw"] * (1.0 / 60.0)

            # 2. Step AI Solution
            sensor_data = {
                "temp": plant_ai.temp,
                "rh": plant_ai.rh,
                "dp": -5.0 if sensor_glitch[idx] else plant_ai.dp,
                "particle_count": plant_ai.particle_count
            }
            cmd_ai = ctrl_ai.optimize_setpoints(sensor_data, q_mes[idx], particle_gen[idx])
            if ai_fault[idx]:
                cmd_ai = ctrl_ai.plc.check_and_filter(0.20, 0.25, sensor_data)

            res_ai = plant_ai.step(
                cmd_ai["u_mau"], cmd_ai["u_ffu"], q_mes[idx], particle_gen[idx],
                exhaust_override=exhaust_override[idx], dt_sec=60.0
            )
            tracker["energy_ai"] += res_ai["p_total_kw"] * (1.0 / 60.0)

            # Record
            tracker["time"].append(t_hr)
            tracker["p_base"].append(res_b["p_total_kw"])
            tracker["p_ai"].append(res_ai["p_total_kw"])
            tracker["e_base"].append(tracker["energy_base"])
            tracker["e_ai"].append(tracker["energy_ai"])
            tracker["dp_base"].append(res_b["dp"])
            tracker["dp_ai"].append(res_ai["dp"])
            tracker["part_base"].append(res_b["particle_count"])
            tracker["part_ai"].append(res_ai["particle_count"])
            tracker["plc_status"].append(cmd_ai["status"])

            tracker["step"] += 1

        t_data = tracker["time"]
        line_p_base.set_data(t_data, tracker["p_base"])
        line_p_ai.set_data(t_data, tracker["p_ai"])
        line_e_base.set_data(t_data, tracker["e_base"])
        line_e_ai.set_data(t_data, tracker["e_ai"])
        line_dp_base.set_data(t_data, tracker["dp_base"])
        line_dp_ai.set_data(t_data, tracker["dp_ai"])
        line_c_base.set_data(t_data, tracker["part_base"])
        line_c_ai.set_data(t_data, tracker["part_ai"])

        # Update banner status
        last_t = t_data[-1]
        hr = int(last_t)
        mn = int((last_t - hr) * 60)
        cur_savings = ((tracker["energy_base"] - tracker["energy_ai"]) / max(0.1, tracker["energy_base"])) * 100.0
        cur_status = tracker["plc_status"][-1]
        cur_q = q_mes[tracker["step"] - 1]

        # MES Phase determination
        if 0.0 <= last_t < 6.0:
            mes_phase = "Ca Đêm: Chờ"
        elif 6.0 <= last_t < 8.0:
            mes_phase = "Giao Ca: Gia Nhiệt"
        elif 8.0 <= last_t < 11.5:
            mes_phase = "Ca Sáng: Lot A UV (90kW)"
        elif 11.5 <= last_t < 11.75:
            mes_phase = "⚠️ SỰ CỐ: Cửa Mở"
        elif 11.75 <= last_t < 12.0:
            mes_phase = "Ca Sáng: Hoàn Tất Lot A"
        elif 12.0 <= last_t < 13.0:
            mes_phase = "Nghỉ Trưa (60kW)"
        elif 13.0 <= last_t < 16.5:
            mes_phase = "Ca Chiều: Lot B DUV (88kW)"
        elif 16.5 <= last_t < 16.75:
            mes_phase = "⚠️ CẢM BIẾN: Nhiễu EMI"
        elif 16.75 <= last_t < 18.0:
            mes_phase = "Ca Chiều: Hoàn Tất Lot B"
        elif 18.0 <= last_t < 22.0:
            mes_phase = "Ca Tối: Track Run (50kW)"
        else:
            mes_phase = "Ca Đêm: Chờ Nạp Lot"

        if cur_status == "FAIL_SAFE_ACTIVE":
            status_text.set_text(
                f"[{hr:02d}:{mn:02d}] MES: {mes_phase} | ⚠️ PLC FAIL-SAFE ACTIVE (Quạt 95%) | Tiết kiệm: {cur_savings:.1f}% | AI: {tracker['p_ai'][-1]:.1f} kW vs Base: {tracker['p_base'][-1]:.1f} kW"
            )
            status_text.set_backgroundcolor("#fee2e2")
            status_text.get_bbox_patch().set_edgecolor("#ef4444")
        else:
            status_text.set_text(
                f"[{hr:02d}:{mn:02d}] MES: {mes_phase} (Q={cur_q:.0f}kW) |  AI OPTIMIZING (PLC SAFE) | Tiết kiệm: {cur_savings:.1f}% | AI: {tracker['p_ai'][-1]:.1f} kW (Base: {tracker['p_base'][-1]:.1f} kW)"
            )
            status_text.set_backgroundcolor("#ecfdf5")
            status_text.get_bbox_patch().set_edgecolor("#10b981")

        return line_p_base, line_p_ai, line_e_base, line_e_ai, line_dp_base, line_dp_ai, line_c_base, line_c_ai

    anim = FuncAnimation(fig, update_frame, interval=50, blit=False)
    plt.show()

if __name__ == "__main__":
    speed = 10
    if len(sys.argv) > 1:
        try:
            speed = int(sys.argv[1])
        except ValueError:
            pass
    run_interactive_comparison(speed_factor=speed)
