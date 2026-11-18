"""
Interactive Real-Time Desktop Visualizer for Baseline Cleanroom Simulation
Showcases:
1. MES Production Schedule & Lithography Thermal / Particle Disturbances
2. Baseline Traditional Fixed Fan Operation (95% MAU / 100% FFU Constant)
3. Differential Pressure & ISO Class 3 Particle Curves
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
from baseline_controller import BaselineController


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
        return "⚡ Cảm Biến: Nhiễu Xung Điện Từ EMI", "#ea580c"
    elif 16.75 <= t_hr < 18.0:
        return "Ca Chiều: Hoàn Tất Tráng Keo & Phơi Sáng Lot B", "#7c3aed"
    elif 18.0 <= t_hr < 22.0:
        return "Ca Tối: Xử Lý Track Coater & Developer Phụ (50 kW)", "#0891b2"
    else:
        return "Ca Đêm: Kết Thúc Mẻ / Chờ Nạp Phôi Mới (28 kW)", "#64748b"


def run_interactive_simulation(speed_factor=10):
    """
    speed_factor: Number of simulation minutes advanced per frame update.
    Default 10 = fast, smooth real-time visualization of 24h.
    """
    print("=" * 75)
    print("  LAUNCHING INTERACTIVE CLEANROOM SIMULATION (01_BASELINE)")
    print("  MES Production Schedule + Traditional Constant Fan Operation")
    print("=" * 75)
    print(f"-> Speed Factor: {speed_factor} sim-minutes per frame")
    print("-> Close the window or press Ctrl+C in terminal to stop.\n")

    n_steps = 1440
    times_hr, q_mes, particle_gen, exhaust_override, sensor_glitch, ai_fault = get_standard_mes_scenario(n_steps)

    plant = CleanroomPlant()
    controller = BaselineController(u_mau=0.95, u_ffu=1.00)

    # Pre-allocate data structures
    history = {
        "step": [],
        "time_hr": [],
        "q_mes": [],
        "particle_gen": [],
        "power_kw": [],
        "u_mau": [],
        "u_ffu": [],
        "dp": [],
        "particles": [],
        "temp": [],
        "cum_kwh": []
    }

    # Setup Figure and Subplots (5 subplots identical to AI solution layout)
    fig, axs = plt.subplots(5, 1, figsize=(13, 10.5))
    fig.canvas.manager.set_window_title("SemiconFab Digital Twin - 01_Baseline MES Schedule & Live Simulation")
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

    lines_0 = [line_q_mes, line_p_gen]
    labels_0 = [l.get_label() for l in lines_0]
    ax_mes.legend(lines_0, labels_0, loc="upper right", fontsize=8.5)

    # -------------------------------------------------------------
    # 1. Fan Electrical Power (kW)
    # -------------------------------------------------------------
    line_power, = axs[1].plot([], [], color='#dc2626', lw=2.2, label="Baseline Fan Power (Constant 23.4 kW)")
    axs[1].axhline(11.53, color='#16a34a', linestyle='--', lw=1.5, label="AI Solution Avg Power Target (11.5 kW)")
    axs[1].set_xlim(0, 24)
    axs[1].set_ylim(0, 26)
    axs[1].set_ylabel("Power (kW)", fontweight='bold')
    axs[1].set_title("1. Baseline: Tiêu Thụ Điện Quạt Cố Định 100% (Lãng Phí Khi Không Tải)", fontsize=10.5, fontweight='bold')
    axs[1].grid(True, alpha=0.3)
    axs[1].legend(loc="upper right", fontsize=8.5)

    # -------------------------------------------------------------
    # 2. Fan Speed Setpoints (%)
    # -------------------------------------------------------------
    line_mau, = axs[2].plot([], [], color='#2563eb', lw=2.0, label="Baseline MAU Speed (95% Cố Định)")
    line_ffu, = axs[2].plot([], [], color='#0d9488', lw=2.0, label="Baseline FFU Speed (100% Cố Định)")
    axs[2].set_xlim(0, 24)
    axs[2].set_ylim(35, 105)
    axs[2].set_ylabel("Speed (%)", fontweight='bold')
    axs[2].set_title("2. Điểm Đặt Quạt Baseline: Chạy Cố Định Tuyệt Đối (Không Thích Ứng MES)", fontsize=10.5, fontweight='bold')
    axs[2].grid(True, alpha=0.3)
    axs[2].legend(loc="lower right", fontsize=8.5)

    # -------------------------------------------------------------
    # 3. Cleanroom Positive Differential Pressure (Delta P)
    # -------------------------------------------------------------
    line_dp, = axs[3].plot([], [], color='#d97706', lw=2.2, label="Baseline Delta P (Pa)")
    axs[3].axhline(15.0, color='#dc2626', linestyle='--', lw=1.5, label="Ngưỡng Bảo Vệ Tối Thiểu (15 Pa)")
    axs[3].fill_between([0, 24], 15.0, 35.0, color='#10b981', alpha=0.08, label="Vùng An Toàn (>= 15 Pa)")
    axs[3].set_xlim(0, 24)
    axs[3].set_ylim(10, 32)
    axs[3].set_ylabel("Delta P (Pa)", fontweight='bold')
    axs[3].set_title("3. Chênh Áp Dương Buồng Sạch & Nguy Cơ Khi Mở Cửa (Differential Pressure)", fontsize=10.5, fontweight='bold')
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
        "Đang khởi động Baseline Simulation & Lịch trình MES...",
        ha="center", va="center", fontsize=11, fontweight='bold',
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#fef2f2", edgecolor="#ef4444", lw=1.4)
    )

    state_tracker = {
        "current_step": 0,
        "cum_energy": 0.0
    }

    # Vertical cursor line to indicate simulation time on all plots
    time_cursors = [ax.axvline(0, color='#475569', linestyle='-', lw=1.2, alpha=0.7) for ax in axs]

    def update_frame(frame):
        curr = state_tracker["current_step"]
        if curr >= n_steps:
            status_text.set_text(
                f"HOÀN TẤT 24H BASELINE | Tổng điện: {state_tracker['cum_energy']:.1f} kWh (Không Tiết Kiệm) | Quạt chạy 100% liên tục"
            )
            status_text.set_backgroundcolor("#fee2e2")
            return line_q_mes, line_p_gen, line_power, line_mau, line_ffu, line_dp, line_part

        # Run speed_factor steps
        end_step = min(n_steps, curr + speed_factor)
        for i in range(curr, end_step):
            state = {
                "temp": plant.temp,
                "rh": plant.rh,
                "dp": plant.dp,
                "particle_count": plant.particle_count
            }
            cmd = controller.get_setpoints(state, q_mes[i])
            res = plant.step(
                cmd["u_mau"], cmd["u_ffu"],
                q_mes[i], particle_gen[i],
                exhaust_override=exhaust_override[i],
                dt_sec=60.0
            )

            state_tracker["cum_energy"] += res["p_total_kw"] * (1.0 / 60.0)
            history["step"].append(i)
            history["time_hr"].append(times_hr[i])
            history["q_mes"].append(q_mes[i])
            history["particle_gen"].append(particle_gen[i])
            history["power_kw"].append(res["p_total_kw"])
            history["u_mau"].append(cmd["u_mau"] * 100.0)
            history["u_ffu"].append(cmd["u_ffu"] * 100.0)
            history["dp"].append(res["dp"])
            history["particles"].append(res["particle_count"])
            history["temp"].append(res["temp"])
            history["cum_kwh"].append(state_tracker["cum_energy"])

        state_tracker["current_step"] = end_step
        t_data = history["time_hr"]

        # Update lines
        line_q_mes.set_data(t_data, history["q_mes"])
        line_p_gen.set_data(t_data, history["particle_gen"])
        line_power.set_data(t_data, history["power_kw"])
        line_mau.set_data(t_data, history["u_mau"])
        line_ffu.set_data(t_data, history["u_ffu"])
        line_dp.set_data(t_data, history["dp"])
        line_part.set_data(t_data, history["particles"])

        # Update time cursor
        last_t = t_data[-1]
        for cur in time_cursors:
            cur.set_xdata([last_t, last_t])

        hours = int(last_t)
        minutes = int((last_t - hours) * 60)
        clock_str = f"{hours:02d}:{minutes:02d}"

        cur_q = history["q_mes"][-1]
        cur_p = history["power_kw"][-1]
        cur_dp = history["dp"][-1]
        cur_c = history["particles"][-1]
        cum_e = state_tracker["cum_energy"]

        mes_desc, _ = get_mes_phase_info(last_t)

        status_text.set_text(
            f"[{clock_str}] MES: {mes_desc} | BASELINE TRUYỀN THỐNG (CỐ ĐỊNH 100%) | Quạt: {cur_p:.1f} kW | Đã dùng: {cum_e:.1f} kWh | dP: {cur_dp:.1f} Pa"
        )
        status_text.set_backgroundcolor("#fef2f2")
        status_text.get_bbox_patch().set_edgecolor("#ef4444")

        return line_q_mes, line_p_gen, line_power, line_mau, line_ffu, line_dp, line_part

    total_frames = int(np.ceil(n_steps / speed_factor)) + 10
    anim = FuncAnimation(fig, update_frame, frames=total_frames, interval=50, blit=False, repeat=False)
    plt.show()


if __name__ == "__main__":
    speed = 10
    if len(sys.argv) > 1:
        try:
            speed = int(sys.argv[1])
        except ValueError:
            pass
    run_interactive_simulation(speed_factor=speed)
