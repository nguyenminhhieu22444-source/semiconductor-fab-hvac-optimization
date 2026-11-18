"""
Interactive Real-Time Desktop Visualizer for AI-Driven Cleanroom Simulation
Showcases:
1. MES Production Schedule & Lithography Thermal / Particle Disturbances
2. Data Processing & AI State Prediction (PINN / Physics-Informed Surrogate)
3. AI Energy Optimizer (Constrained SLSQP Optimizer)
4. PLC Safety Gatekeeper & Fail-Safe Fallback Interlock in Real Time
"""
import os
import sys
import numpy as np
import matplotlib
# Use TkAgg for native Windows desktop interactive GUI
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Import model components
from cleanroom_model import CleanroomPlant, get_standard_mes_scenario
from ai_controller import AIEnergyOptimizer


def get_mes_phase_info(t_hr):
    """
    Returns MES lot production stage title and descriptive badge color based on simulation time.
    """
    if 0.0 <= t_hr < 6.0:
        return "Ca Đêm: Chế Độ Chờ / Chamber Standby (25 kW)", "#64748b"
    elif 6.0 <= t_hr < 8.0:
        return "Giao Ca: Gia Nhiệt Buồng Track & Chuẩn Bị Lot A (25->90 kW)", "#d97706"
    elif 8.0 <= t_hr < 11.5:
        return "Ca Sáng: Quang Khắc UV Lot A (Peak 90 kW)", "#0284c7"
    elif 11.5 <= t_hr < 11.75:
        return "⚠️ Sự Cố MES: Cửa Mở Bảo Dưỡng Đột Xuất (Rò Rỉ)", "#dc2626"
    elif 11.75 <= t_hr < 12.0:
        return "Ca Sáng: Khôi Phục & Hoàn Tất Lot A", "#0284c7"
    elif 12.0 <= t_hr < 13.0:
        return "Nghỉ Trưa: Bán Tải Stepper Standby (60 kW)", "#ca8a04"
    elif 13.0 <= t_hr < 16.5:
        return "Ca Chiều: Quang Khắc Ngập DUV Lot B (Peak 88 kW)", "#7c3aed"
    elif 16.5 <= t_hr < 16.75:
        return "⚠️ Cảm Biến Lỗi: Nhiễu Xung Điện Từ EMI", "#ea580c"
    elif 16.75 <= t_hr < 18.0:
        return "Ca Chiều: Hoàn Tất Tráng Keo & Phơi Sáng Lot B", "#7c3aed"
    elif 18.0 <= t_hr < 22.0:
        return "Ca Tối: Xử Lý Track Coater & Developer Phụ (50 kW)", "#0891b2"
    else:
        return "Ca Đêm: Kết Thúc Mẻ / Chờ Nạp Phôi Mới (28 kW)", "#64748b"


def run_interactive_ai_simulation(speed_factor=10):
    """
    speed_factor: Number of simulation minutes advanced per animation frame.
    Default 10 = fast, smooth 24h interactive execution.
    """
    print("=" * 75)
    print("  LAUNCHING INTERACTIVE CLEANROOM AI SIMULATION (02_AI_SOLUTION)")
    print("  MES Production Schedule + PINN Surrogate + SLSQP + PLC Gatekeeper")
    print("=" * 75)
    print(f"-> Speed Factor: {speed_factor} sim-minutes per frame")
    print("-> Close the window or press Ctrl+C in terminal to stop.\n")

    n_steps = 1440
    times_hr, q_mes, particle_gen, exhaust_override, sensor_glitch, ai_fault = get_standard_mes_scenario(n_steps)

    plant = CleanroomPlant()
    ai_optimizer = AIEnergyOptimizer(plant)

    # Historical data tracking
    history = {
        "step": [],
        "time_hr": [],
        "q_mes": [],
        "particle_gen": [],
        "power_kw": [],
        "cum_energy_kwh": [],
        "u_mau": [],
        "u_ffu": [],
        "dp": [],
        "particles": [],
        "temp": [],
        "plc_status": [],
        "failsafe_active": []
    }

    # Setup interactive figure with 5 subplots
    fig, axs = plt.subplots(5, 1, figsize=(13, 10.5))
    fig.canvas.manager.set_window_title("SemiconFab Digital Twin - MES Schedule & AI Solution Live Simulation")
    plt.subplots_adjust(hspace=0.52, top=0.93, bottom=0.05, left=0.08, right=0.92)

    # -------------------------------------------------------------
    # 0. MES Production Schedule & Litho Equipment Load
    # -------------------------------------------------------------
    ax_mes = axs[0]
    ax_mes_twin = ax_mes.twinx()

    # Pre-render MES shift schedule background blocks
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
        ax_mes.axvspan(start, end, color=col, alpha=0.55)
        ax_mes.text((start + end) / 2.0, 93, lbl, ha='center', va='top', fontsize=8.5, fontweight='bold', color='#475569')

    # Event indicators on MES timeline
    ax_mes.axvline(11.5, color='#ef4444', linestyle=':', lw=1.5)
    ax_mes.text(11.5, 30, "11:30 Cửa Mở", color='#b91c1c', fontsize=8, fontweight='bold', rotation=90, va='bottom', ha='right')
    ax_mes.axvline(16.5, color='#ea580c', linestyle=':', lw=1.5)
    ax_mes.text(16.5, 30, "16:30 Nhiễu EMI", color='#c2410c', fontsize=8, fontweight='bold', rotation=90, va='bottom', ha='right')

    line_q_mes, = ax_mes.plot([], [], color='#ea580c', lw=2.2, label="Tải nhiệt máy quang khắc Q_MES (kW)")
    line_p_gen, = ax_mes_twin.plot([], [], color='#8b5cf6', linestyle='--', lw=1.4, alpha=0.85, label="Bụi sinh ra do nhân sự P_gen (/min)")

    ax_mes.set_xlim(0, 24)
    ax_mes.set_ylim(10, 115)
    ax_mes_twin.set_ylim(0, 1000)
    ax_mes.set_ylabel("Q_MES (kW)", fontweight='bold', color='#ea580c')
    ax_mes_twin.set_ylabel("P_gen (/min)", fontweight='bold', color='#8b5cf6')
    ax_mes.set_title("0. Lịch Trình Sản Xuất MES & Tải Nhiệt Máy Quang Khắc (Litho Exposure & Track Schedule)", fontsize=10.5, fontweight='bold')
    ax_mes.grid(True, alpha=0.25)

    # Combine legends for twin axis
    lines_0 = [line_q_mes, line_p_gen]
    labels_0 = [l.get_label() for l in lines_0]
    ax_mes.legend(lines_0, labels_0, loc="upper right", fontsize=8.5)

    # -------------------------------------------------------------
    # 1. Fan Electrical Power (kW)
    # -------------------------------------------------------------
    line_power, = axs[1].plot([], [], color='#16a34a', lw=2.2, label="AI Dynamic Fan Power (kW)")
    axs[1].axhline(23.42, color='#dc2626', linestyle='--', lw=1.5, label="Baseline Constant Power (23.4 kW)")
    axs[1].set_xlim(0, 24)
    axs[1].set_ylim(0, 26)
    axs[1].set_ylabel("Power (kW)", fontweight='bold')
    axs[1].set_title("1. AI Energy Optimizer: Tiêu Thụ Điện Thực Tế vs Baseline (Tiết kiệm ~50.8%)", fontsize=10.5, fontweight='bold')
    axs[1].grid(True, alpha=0.3)
    axs[1].legend(loc="upper right", fontsize=8.5)

    # -------------------------------------------------------------
    # 2. Dynamic Setpoints & PLC Safety States
    # -------------------------------------------------------------
    line_mau, = axs[2].plot([], [], color='#2563eb', lw=2.0, label="MAU Speed Setpoint (%)")
    line_ffu, = axs[2].plot([], [], color='#0d9488', lw=2.0, label="FFU Speed Setpoint (%)")
    axs[2].axhline(95.0, color='#93c5fd', linestyle=':', lw=1.2, label="Baseline MAU (95%)")
    axs[2].axhline(100.0, color='#5eead4', linestyle=':', lw=1.2, label="Baseline FFU (100%)")
    axs[2].set_xlim(0, 24)
    axs[2].set_ylim(35, 105)
    axs[2].set_ylabel("Speed (%)", fontweight='bold')
    axs[2].set_title("2. Điểm Đặt Điều Khiển MAU & FFU & Giám Sát Chốt PLC Gatekeeper", fontsize=10.5, fontweight='bold')
    axs[2].grid(True, alpha=0.3)
    axs[2].legend(loc="lower right", fontsize=8.5)

    # -------------------------------------------------------------
    # 3. Cleanroom Positive Differential Pressure (Delta P)
    # -------------------------------------------------------------
    line_dp, = axs[3].plot([], [], color='#059669', lw=2.2, label="Positive Pressure Delta P (Pa)")
    axs[3].axhline(15.0, color='#dc2626', linestyle='--', lw=1.5, label="Ngưỡng Bảo Vệ Tối Thiểu (15 Pa)")
    axs[3].fill_between([0, 24], 15.0, 35.0, color='#10b981', alpha=0.08, label="Vùng An Toàn (>= 15 Pa)")
    axs[3].set_xlim(0, 24)
    axs[3].set_ylim(10, 32)
    axs[3].set_ylabel("Delta P (Pa)", fontweight='bold')
    axs[3].set_title("3. Chênh Áp Dương Buồng Sạch & Bảo Vệ Cửa Rò Rỉ (Differential Pressure Cascade)", fontsize=10.5, fontweight='bold')
    axs[3].grid(True, alpha=0.3)
    axs[3].legend(loc="lower right", fontsize=8.5)

    # -------------------------------------------------------------
    # 4. Particle Concentration & ISO Class 3 Compliance
    # -------------------------------------------------------------
    line_part, = axs[4].plot([], [], color='#7c3aed', lw=2.0, label="Hạt bụi 0.5 µm / m³")
    axs[4].axhline(1000.0, color='#b91c1c', linestyle='--', lw=1.5, label="Giới Hạn Tối Đa ISO Class 3 (1000)")
    axs[4].fill_between([0, 24], 0, 1000.0, color='#8b5cf6', alpha=0.06, label="Đạt Chuẩn ISO Class 3")
    axs[4].set_xlim(0, 24)
    axs[4].set_ylim(0, 1100)
    axs[4].set_xlabel("Thời Gian Mô Phỏng (Giờ trong ngày)", fontweight='bold')
    axs[4].set_ylabel("Hạt / m³", fontweight='bold')
    axs[4].set_title("4. Nồng Độ Bụi Lơ Lửng & Chuẩn Sạch ISO 14644-1 Class 3", fontsize=10.5, fontweight='bold')
    axs[4].grid(True, alpha=0.3)
    axs[4].legend(loc="upper right", fontsize=8.5)

    # Top Status Banner Text
    status_text = fig.text(
        0.50, 0.968,
        "Đang khởi động mô hình AI & Lịch trình MES...",
        ha="center", va="center", fontsize=11, fontweight='bold',
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#ecfdf5", edgecolor="#10b981", lw=1.4)
    )

    state_tracker = {
        "current_step": 0,
        "cum_energy": 0.0,
        "failsafe_minutes": 0
    }

    # Vertical cursor line to indicate simulation time on all plots
    time_cursors = [ax.axvline(0, color='#475569', linestyle='-', lw=1.2, alpha=0.7) for ax in axs]

    def update_frame(frame):
        curr = state_tracker["current_step"]
        if curr >= n_steps:
            pct_saved = ((562.10 - state_tracker["cum_energy"]) / 562.10) * 100.0
            status_text.set_text(
                f"HOÀN TẤT 24H | Điện tiêu thụ: {state_tracker['cum_energy']:.1f} kWh (Tiết kiệm -{pct_saved:.1f}%) | PLC Fail-Safe: {state_tracker['failsafe_minutes']} phút"
            )
            status_text.set_backgroundcolor("#dcfce7")
            return line_q_mes, line_p_gen, line_power, line_mau, line_ffu, line_dp, line_part

        # Advance simulation by speed_factor steps
        steps_to_run = min(speed_factor, n_steps - curr)
        for _ in range(steps_to_run):
            idx = state_tracker["current_step"]
            t_hr = times_hr[idx]

            sensor_data = {
                "temp": plant.temp,
                "rh": plant.rh,
                "dp": -5.0 if sensor_glitch[idx] else plant.dp,
                "particle_count": plant.particle_count
            }

            cmd = ai_optimizer.optimize_setpoints(sensor_data, q_mes[idx], particle_gen[idx])

            # Injected AI fault check
            if ai_fault[idx]:
                cmd = ai_optimizer.plc.check_and_filter(0.20, 0.25, sensor_data)

            res = plant.step(
                cmd["u_mau"], cmd["u_ffu"], q_mes[idx], particle_gen[idx],
                exhaust_override=exhaust_override[idx], dt_sec=60.0
            )

            state_tracker["cum_energy"] += res["p_total_kw"] * (1.0 / 60.0)
            is_fs = (cmd["status"] == "FAIL_SAFE_ACTIVE")
            if is_fs:
                state_tracker["failsafe_minutes"] += 1

            # Append to history
            history["step"].append(idx)
            history["time_hr"].append(t_hr)
            history["q_mes"].append(q_mes[idx])
            history["particle_gen"].append(particle_gen[idx])
            history["power_kw"].append(res["p_total_kw"])
            history["cum_energy_kwh"].append(state_tracker["cum_energy"])
            history["u_mau"].append(cmd["u_mau"] * 100.0)
            history["u_ffu"].append(cmd["u_ffu"] * 100.0)
            history["dp"].append(res["dp"])
            history["particles"].append(res["particle_count"])
            history["temp"].append(res["temp"])
            history["plc_status"].append(cmd["status"])
            history["failsafe_active"].append(is_fs)

            state_tracker["current_step"] += 1

        # Update plot lines
        t_data = history["time_hr"]
        line_q_mes.set_data(t_data, history["q_mes"])
        line_p_gen.set_data(t_data, history["particle_gen"])
        line_power.set_data(t_data, history["power_kw"])
        line_mau.set_data(t_data, history["u_mau"])
        line_ffu.set_data(t_data, history["u_ffu"])
        line_dp.set_data(t_data, history["dp"])
        line_part.set_data(t_data, history["particles"])

        # Current state values for banner
        last_t = t_data[-1]
        for cur in time_cursors:
            cur.set_xdata([last_t, last_t])

        hr_int = int(last_t)
        min_int = int((last_t - hr_int) * 60)
        clock_str = f"{hr_int:02d}:{min_int:02d}"

        cur_q = history["q_mes"][-1]
        cur_p = history["power_kw"][-1]
        cur_dp = history["dp"][-1]
        cur_c = history["particles"][-1]
        cur_status = history["plc_status"][-1]
        cum_e = state_tracker["cum_energy"]

        mes_desc, _ = get_mes_phase_info(last_t)

        # Base energy consumed up to this point
        base_e_so_far = 23.42 * last_t
        saved_pct = ((base_e_so_far - cum_e) / max(0.1, base_e_so_far)) * 100.0

        if cur_status == "FAIL_SAFE_ACTIVE":
            status_text.set_text(
                f"[{clock_str}] MES: {mes_desc} | ⚠️ PLC FAIL-SAFE ACTIVE (Quạt 95%) | dP: {cur_dp:.1f} Pa | Tiết kiệm: {saved_pct:.1f}%"
            )
            status_text.set_backgroundcolor("#fee2e2")
            status_text.get_bbox_patch().set_edgecolor("#ef4444")
        else:
            status_text.set_text(
                f"[{clock_str}] MES: {mes_desc} |  PLC SAFE (AI OPTIMIZED) | Q_MES: {cur_q:.0f}kW | Quạt: {cur_p:.1f}kW | Tiết kiệm: {saved_pct:.1f}%"
            )
            status_text.set_backgroundcolor("#ecfdf5")
            status_text.get_bbox_patch().set_edgecolor("#10b981")

        return line_q_mes, line_p_gen, line_power, line_mau, line_ffu, line_dp, line_part

    # Run animation at 50ms per frame
    anim = FuncAnimation(fig, update_frame, interval=50, blit=False)
    plt.show()


if __name__ == "__main__":
    speed = 10
    if len(sys.argv) > 1:
        try:
            speed = int(sys.argv[1])
        except ValueError:
            pass
    run_interactive_ai_simulation(speed_factor=speed)
