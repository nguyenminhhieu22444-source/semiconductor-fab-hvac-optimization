"""
run_interactive_scenarios.py
Interactive Live GUI & Benchmark Runner for 5 Semiconductor Cleanroom Scenarios.
Features real-time animated multi-physics visualizer, side-by-side baseline vs direct AI,
and interactive terminal control.
"""
import os
import sys

# Force interactive TkAgg backend before importing pyplot
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import json
import numpy as np

# Ensure root paths are in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(os.path.join(root_dir, "01_baseline"))
sys.path.append(os.path.join(root_dir, "02_ai_solution"))
sys.path.append(current_dir)

from cleanroom_model import CleanroomPlant
from bay1_simulation import simulation_step
from ai_controller import DirectFanController
from scenarios_config import get_all_scenarios

# Global reference to keep animation object alive in memory
active_animation = None


def run_live_gui_scenario(scenario_data, speed_factor=10):
    """
    Launch real-time desktop GUI animated simulation for the selected scenario.
    speed_factor: simulation minutes advanced per frame (10 = smooth 24h animation).
    """
    global active_animation

    sc_id = scenario_data.get("id", "scenario_1")
    sc_name = scenario_data["name"]
    sc_desc = scenario_data["description"]
    times_hr = scenario_data["times_hr"]
    n_steps = len(times_hr)
    q_mes = scenario_data["q_mes"]
    particle_gen = scenario_data["particle_gen"]
    exhaust_override = scenario_data["exhaust_override"]
    outdoor_temp = scenario_data.get("outdoor_temp", np.full(n_steps, 29.93))
    outdoor_rh = scenario_data.get("outdoor_rh", np.full(n_steps, 80.0))
    amc_mult = scenario_data.get("amc_multiplier", np.ones(n_steps))

    print(f"\n[+] Đang mở cửa sổ mô phỏng đồ họa cho: {sc_name}")
    print(f"    Mô tả đặc thù: {sc_desc}")
    print("    -> Cửa sổ đồ họa thời gian thực đang hiển thị trên màn hình của bạn.")
    print("    -> Đóng cửa sổ đồ họa sau khi xem xong để nhận báo cáo số liệu.\n")

    # Plants for simultaneous execution
    plant_base = CleanroomPlant()
    plant_ai = CleanroomPlant()
    ctrl_ai = DirectFanController(plant_ai)

    # Histories
    hist = {
        "time_hr": [],
        "p_base": [],
        "p_ai": [],
        "energy_base": [],
        "energy_ai": [],
        "u_mau_ai": [],
        "u_ffu_ai": [],
        "dp_base": [],
        "dp_ai": [],
        "particles_base": [],
        "particles_ai": [],
        "amc_ai": [],
        "plc_failsafe": []
    }

    cum_e_base = 0.0
    cum_e_ai = 0.0

    # Setup 4-row live comparison plot
    fig, axs = plt.subplots(4, 1, figsize=(14, 10.5))
    fig.canvas.manager.set_window_title(f"SemiconFab 300mm Live Twin - {sc_name}")
    plt.subplots_adjust(hspace=0.48, top=0.90, bottom=0.06, left=0.08, right=0.92)

    # Bring window to foreground on Windows desktop
    try:
        win = fig.canvas.manager.window
        win.lift()
        win.attributes('-topmost', True)
        win.after_idle(win.attributes, '-topmost', False)
    except Exception:
        pass

    # Status banner top
    banner_colors = {
        "scenario_1": ("#e0f2fe", "#0284c7"),
        "scenario_2": ("#fee2e2", "#ef4444"),
        "scenario_3": ("#ffedd5", "#ea580c"),
        "scenario_4": ("#f3e8ff", "#9333ea"),
        "scenario_5": ("#ecfdf5", "#10b981")
    }
    bg_c, border_c = banner_colors.get(sc_id, ("#e0f2fe", "#0284c7"))

    status_text = fig.text(
        0.5, 0.95,
        f"[{sc_name.split(':')[0].upper()}] Đang chạy mô phỏng: {sc_desc}",
        ha='center', va='center', fontsize=10.5, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.5', facecolor=bg_c, edgecolor=border_c, lw=1.5)
    )

    # 1. Panel 0: Scenario Disturbances (Adaptive per scenario)
    ax_dist = axs[0]
    ax_dist_twin = ax_dist.twinx()

    if sc_id == "scenario_1":
        line_q, = ax_dist.plot([], [], color='#ea580c', lw=2.0, label="Tải nhiệt máy Q_mes (kW)")
        line_p, = ax_dist_twin.plot([], [], color='#8b5cf6', linestyle='--', lw=1.5, label="Bụi sinh ra P_gen (/min)")
        ax_dist.set_xlim(0, 24)
        ax_dist.set_ylim(0, 120)
        ax_dist_twin.set_ylim(0, 800)
        ax_dist.set_ylabel("Nhiệt (kW)", color='#ea580c', fontweight='bold')
        ax_dist_twin.set_ylabel("Bụi (/min)", color='#8b5cf6', fontweight='bold')
        ax_dist.set_title("1. [KỊCH BẢN 1] Chu Trình 24H Chuẩn: Ca Ngày (90 kW - 8,500 m3/h) ⟷ Ca Đêm Tiết Lưu (25 kW - 5,000 m3/h)", fontsize=9.5, fontweight='bold', color='#0369a1')
        lines_0 = [line_q, line_p]

    elif sc_id == "scenario_2":
        line_q, = ax_dist.plot([], [], color='#ea580c', lw=1.8, label="Tải nhiệt máy Q_mes (kW)")
        line_exh, = ax_dist_twin.plot([], [], color='#dc2626', lw=2.4, label="Khí xả buồng đột biến (m3/h)")
        ax_dist.axvspan(11.5, 12.0, color='#fee2e2', alpha=0.7, label="⚠️ SỰ CỐ MỞ CỬA BUỒNG SẠCH (11h30 - 12h00)")
        ax_dist.set_xlim(0, 24)
        ax_dist.set_ylim(0, 120)
        ax_dist_twin.set_ylim(4000, 12000)
        ax_dist.set_ylabel("Nhiệt (kW)", color='#ea580c', fontweight='bold')
        ax_dist_twin.set_ylabel("Khí xả (m3/h)", color='#dc2626', fontweight='bold')
        ax_dist.set_title("1. [KỊCH BẢN 2] Sự Cố Mở Cửa Buồng (11h30-12h00): Bụi tràn +750/min, Khí xả vọt 10,800 m3/h!", fontsize=9.5, fontweight='bold', color='#b91c1c')
        lines_0 = [line_q, line_exh]

    elif sc_id == "scenario_3":
        line_temp, = ax_dist.plot([], [], color='#dc2626', lw=2.4, label="Nhiệt độ ngoài trời T_out (°C)")
        line_rh, = ax_dist_twin.plot([], [], color='#0284c7', linestyle='--', lw=2.0, label="Độ ẩm ngoài trời RH_out (%)")
        ax_dist.axvspan(9.0, 18.0, color='#ffedd5', alpha=0.5, label="☀️ ĐỈNH ĐIỂM SÓNG NHIỆT (Đỉnh 38.5°C, 90% RH)")
        ax_dist.set_xlim(0, 24)
        ax_dist.set_ylim(20, 45)
        ax_dist_twin.set_ylim(50, 100)
        ax_dist.set_ylabel("Nhiệt độ ngoài (°C)", color='#dc2626', fontweight='bold')
        ax_dist_twin.set_ylabel("Độ ẩm ngoài (%)", color='#0284c7', fontweight='bold')
        ax_dist.set_title("1. [KỊCH BẢN 3] Sóng Nhiệt Mùa Hè Cực Hạn Hsinchu: Đỉnh 38.5°C & 90% RH (Tải Tách Ẩm & Sấy Bù Tối Đa)", fontsize=9.5, fontweight='bold', color='#c2410c')
        lines_0 = [line_temp, line_rh]

    elif sc_id == "scenario_4":
        line_amc_in, = ax_dist.plot([], [], color='#7e22ce', lw=2.4, label="Đột biến AMC NH3 ngoài (ppb)")
        line_p, = ax_dist_twin.plot([], [], color='#8b5cf6', linestyle='--', lw=1.5, label="Bụi sinh ra P_gen (/min)")
        ax_dist.axvspan(14.0, 16.5, color='#f3e8ff', alpha=0.7, label="☣️ ĐỘT BIẾN HÓA CHẤT AMC NH3 (Tăng 4.5 lần)")
        ax_dist.axhline(10.0, color='#ef4444', linestyle=':', lw=1.5, label="Ngưỡng thiết kế NH₃ (10 ppb)")
        ax_dist.set_xlim(0, 24)
        ax_dist.set_ylim(0, 50)
        ax_dist_twin.set_ylim(0, 1000)
        ax_dist.set_ylabel("AMC NH3 (ppb)", color='#7e22ce', fontweight='bold')
        ax_dist_twin.set_ylabel("Bụi (/min)", color='#8b5cf6', fontweight='bold')
        ax_dist.set_title("1. [KỊCH BẢN 4] Đột Biến Hóa Chất AMC: Amoniac NH3 tăng 4.5x tại buồng nướng keo Track Coater", fontsize=9.5, fontweight='bold', color='#7e22ce')
        lines_0 = [line_amc_in, line_p]

    else: # scenario_5
        line_q, = ax_dist.plot([], [], color='#059669', lw=2.2, label="Tải máy Stepper Chế Độ Chờ (25 kW Cố định)")
        line_p, = ax_dist_twin.plot([], [], color='#64748b', linestyle='--', lw=1.5, label="Bụi nhân sự tối thiểu (80/min)")
        ax_dist.axhspan(0, 30, color='#ecfdf5', alpha=0.6, label=" Chế độ chờ cuối tuần / Bảo trì máy quang khắc (25 kW)")
        ax_dist.set_xlim(0, 24)
        ax_dist.set_ylim(0, 60)
        ax_dist_twin.set_ylim(0, 400)
        ax_dist.set_ylabel("Nhiệt (kW)", color='#059669', fontweight='bold')
        ax_dist_twin.set_ylabel("Bụi (/min)", color='#64748b', fontweight='bold')
        ax_dist.set_title("1. [KỊCH BẢN 5] Chế Độ Chờ Cuối Tuần: Máy quang khắc 25 kW, Xả 4.800 m³/h", fontsize=9.5, fontweight='bold', color='#047857')
        lines_0 = [line_q, line_p]

    ax_dist.grid(True, alpha=0.25)
    ax_dist.legend(lines_0, [l.get_label() for l in lines_0], loc="upper right", fontsize=8)

    # 2. Panel 1: Fan Electrical Power
    ax_p = axs[1]
    line_p_base, = ax_p.plot([], [], 'r--', lw=1.6, label="Baseline Power (19.7 kW Cố định)")
    line_p_ai, = ax_p.plot([], [], 'g-', lw=2.2, label="AI trực tiếp + PLC")
    ax_p.set_xlim(0, 24)
    ax_p.set_ylim(0, 24)
    ax_p.set_ylabel("Công suất (kW)", fontweight='bold')
    ax_p.set_title("2. Công suất quạt của baseline và AI trực tiếp", fontsize=9.5, fontweight='bold')
    ax_p.grid(True, alpha=0.3)
    ax_p.legend(loc="upper right", fontsize=8)

    # 3. Panel 2: Fan Speeds & PLC Status
    ax_spd = axs[2]
    line_mau_ai, = ax_spd.plot([], [], color='#0284c7', lw=2.0, label="AI MAU VFD Speed (%)")
    line_ffu_ai, = ax_spd.plot([], [], color='#0d9488', lw=2.0, label="AI FFU Speed (%)")
    ax_spd.axhline(95.0, color='r', linestyle=':', label='Baseline MAU (95% - 47.5 Hz)')
    ax_spd.axhline(100.0, color='darkred', linestyle=':', label='Baseline FFU (100%)')
    ax_spd.set_xlim(0, 24)
    ax_spd.set_ylim(35, 105)
    ax_spd.set_ylabel("Tốc độ (%)", fontweight='bold')
    ax_spd.set_title("3. Tốc Độ Quạt Biến Tần VFD MAU & Lưới 48 Quạt Trần FFU", fontsize=9.5, fontweight='bold')
    ax_spd.grid(True, alpha=0.3)
    ax_spd.legend(loc="lower right", fontsize=8)

    # 4. Panel 3: Delta P & Particles
    ax_dp = axs[3]
    ax_c_twin = ax_dp.twinx()
    line_dp_b, = ax_dp.plot([], [], 'r--', lw=1.5, label="Baseline dP (Pa)")
    line_dp_a, = ax_dp.plot([], [], 'g-', lw=2.0, label="AI Solution dP (Pa)")
    ax_dp.axhline(15.0, color='red', linestyle='-', lw=1.8, label="Ngưỡng an toàn ISO (>= 15 Pa)")
    line_c_a, = ax_c_twin.plot([], [], color='#f59e0b', linestyle=':', lw=1.5, label="Bụi nano AI >=0.1µm (/m3)")
    ax_c_twin.axhline(1000.0, color='#dc2626', linestyle=':', lw=1.2, label="Giới hạn ISO Class 3 (<=1,000 /m3)")
    ax_dp.set_xlim(0, 24)
    ax_dp.set_ylim(0, 45)
    ax_c_twin.set_ylim(0, 2500)
    ax_dp.set_xlabel("Thời gian vận hành (Giờ)", fontweight='bold')
    ax_dp.set_ylabel("Chênh áp dP (Pa)", fontweight='bold')
    ax_c_twin.set_ylabel("Bụi nano >=0.1µm (/m3)", color='#f59e0b', fontweight='bold')
    ax_dp.set_title("4. Kiểm Soát Chênh Áp Phòng Sạch & Nồng Độ Bụi Nano (ISO 14644-1:2015 Class 3)", fontsize=9.5, fontweight='bold')
    ax_dp.grid(True, alpha=0.3)
    lines_3 = [line_dp_b, line_dp_a, line_c_a]
    ax_dp.legend(lines_3, [l.get_label() for l in lines_3], loc="upper right", fontsize=8)

    step_idx = [0]

    def update(frame):
        for _ in range(speed_factor):
            i = step_idx[0]
            if i >= n_steps:
                break

            t = times_hr[i]
            _, res_b = simulation_step(plant_base, None, scenario_data, i, "baseline")
            cmd_a, res_a = simulation_step(plant_ai, ctrl_ai, scenario_data, i, "ai")
            dt_hr = scenario_data["dt_sec"] / 3600.0
            nonlocal cum_e_base, cum_e_ai
            cum_e_base += res_b["p_total_kw"] * dt_hr
            cum_e_ai += res_a["p_total_kw"] * dt_hr

            hist["time_hr"].append(t)
            hist["p_base"].append(res_b["p_total_kw"])
            hist["p_ai"].append(res_a["p_total_kw"])
            hist["energy_base"].append(cum_e_base)
            hist["energy_ai"].append(cum_e_ai)
            hist["u_mau_ai"].append(cmd_a["u_mau"] * 100.0)
            hist["u_ffu_ai"].append(cmd_a["u_ffu"] * 100.0)
            hist["dp_base"].append(res_b["dp"])
            hist["dp_ai"].append(res_a["dp"])
            hist["particles_base"].append(res_b["particle_count"])
            hist["particles_ai"].append(res_a["particle_count"])
            hist["amc_ai"].append(res_a["amc_nh3"])
            hist["plc_failsafe"].append(cmd_a["production_hold"])

            step_idx[0] += 1

        if len(hist["time_hr"]) > 0:
            ts = hist["time_hr"]
            if sc_id == "scenario_1":
                line_q.set_data(ts, q_mes[:len(ts)])
                line_p.set_data(ts, particle_gen[:len(ts)])
            elif sc_id == "scenario_2":
                line_q.set_data(ts, q_mes[:len(ts)])
                line_exh.set_data(ts, [exhaust_override[k] * 3600.0 for k in range(len(ts))])
            elif sc_id == "scenario_3":
                line_temp.set_data(ts, outdoor_temp[:len(ts)])
                line_rh.set_data(ts, outdoor_rh[:len(ts)])
            elif sc_id == "scenario_4":
                amc_curve = [5.0 * amc_mult[k] for k in range(len(ts))]
                line_amc_in.set_data(ts, amc_curve)
                line_p.set_data(ts, particle_gen[:len(ts)])
            else:
                line_q.set_data(ts, q_mes[:len(ts)])
                line_p.set_data(ts, particle_gen[:len(ts)])

            line_p_base.set_data(ts, hist["p_base"])
            line_p_ai.set_data(ts, hist["p_ai"])
            line_mau_ai.set_data(ts, hist["u_mau_ai"])
            line_ffu_ai.set_data(ts, hist["u_ffu_ai"])
            ax_dp.set_ylim(min(0, min(hist["dp_base"] + hist["dp_ai"])), max(32, max(hist["dp_base"] + hist["dp_ai"]) * 1.05))
            ax_c_twin.set_ylim(0, max(1100, max(hist["particles_base"] + hist["particles_ai"]) * 1.05))
            line_dp_b.set_data(ts, hist["dp_base"])
            line_dp_a.set_data(ts, hist["dp_ai"])
            line_c_a.set_data(ts, hist["particles_ai"])

            last_t = ts[-1]
            hr_int = int(last_t)
            min_int = int((last_t - hr_int) * 60)
            clock = f"{hr_int:02d}:{min_int:02d}"

            cur_p_ai = hist["p_ai"][-1]
            cur_dp = hist["dp_ai"][-1]
            saved_now = ((cum_e_base - cum_e_ai) / max(0.01, cum_e_base)) * 100.0
            is_fs = hist["plc_failsafe"][-1]

            tag = f"[{sc_name.split(':')[0]}]"
            if is_fs:
                status_text.set_text(f"{tag} [{clock}] ⚠️ GIỮ SẢN XUẤT (PLC mô phỏng) | dP: {cur_dp:.1f} Pa | Tiết kiệm: {saved_now:.1f}%")
                status_text.set_backgroundcolor("#fee2e2")
                status_text.get_bbox_patch().set_edgecolor("#ef4444")
            elif sc_id == "scenario_3":
                cur_tout = outdoor_temp[len(ts)-1]
                cur_rhout = outdoor_rh[len(ts)-1]
                status_text.set_text(f"{tag} [{clock}] ☀️ SÓNG NHIỆT ({cur_tout:.1f}°C, {cur_rhout:.0f}% RH) | Quạt AI: {cur_p_ai:.1f} kW | dP: {cur_dp:.1f} Pa | Tiết kiệm: {saved_now:.1f}%")
                status_text.set_backgroundcolor("#ffedd5")
                status_text.get_bbox_patch().set_edgecolor("#ea580c")
            elif sc_id == "scenario_4":
                cur_amc = hist["amc_ai"][-1]
                status_text.set_text(f"{tag} [{clock}] ☣️ ĐỘT BIẾN AMC NH3: {cur_amc:.1f} ppb | Quạt AI: {cur_p_ai:.1f} kW | dP: {cur_dp:.1f} Pa | Tiết kiệm: {saved_now:.1f}%")
                status_text.set_backgroundcolor("#f3e8ff")
                status_text.get_bbox_patch().set_edgecolor("#9333ea")
            elif sc_id == "scenario_5":
                status_text.set_text(f"{tag} [{clock}]  CHẾ ĐỘ CHỜ CUỐI TUẦN | Quạt AI: {cur_p_ai:.1f} kW | Tiết kiệm điện: {saved_now:.1f}%")
                status_text.set_backgroundcolor("#ecfdf5")
                status_text.get_bbox_patch().set_edgecolor("#10b981")
            else:
                status_text.set_text(f"{tag} [{clock}]  LỆNH ĐẠT KIỂM TRA | Quạt AI: {cur_p_ai:.1f} kW | dP: {cur_dp:.1f} Pa | Tiết kiệm: {saved_now:.1f}%")
                status_text.set_backgroundcolor("#e0f2fe")
                status_text.get_bbox_patch().set_edgecolor("#0284c7")

        return line_p_base, line_p_ai

    n_frames = (n_steps // speed_factor) + 2
    active_animation = FuncAnimation(fig, update, frames=n_frames, interval=30, repeat=False, blit=False)
    plt.show()

    # Once window is closed, compute final summary
    print("\n" + "=" * 72)
    print(f" {sc_name} · Đã chạy {step_idx[0] * scenario_data['dt_sec'] / 60.0:g} phút")
    print("=" * 72)
    saved_kwh = cum_e_base - cum_e_ai
    saved_pct = (saved_kwh / max(0.001, cum_e_base)) * 100.0
    min_dp_b = min(hist['dp_base']) if hist['dp_base'] else 0.0
    min_dp_a = min(hist['dp_ai']) if hist['dp_ai'] else 0.0
    max_part_b = max(hist['particles_base']) if hist['particles_base'] else 0.0
    max_part_a = max(hist['particles_ai']) if hist['particles_ai'] else 0.0
    fs_mins = sum(hist["plc_failsafe"]) * scenario_data["dt_sec"] / 60.0

    print(f"1. Điện quạt baseline {cum_e_base:.2f} kWh")
    print(f"2. Điện quạt AI trực tiếp {cum_e_ai:.2f} kWh")
    print(f"   => Tiết kiệm điện năng quạt:       {saved_kwh:.2f} kWh ({saved_pct:.1f}%)")
    print(f"3. Áp suất phòng dP nhỏ nhất:         Baseline: {min_dp_b:.2f} Pa  |  AI: {min_dp_a:.2f} Pa")
    print(f"4. Nồng độ bụi nano >=0.1µm cực đại:  Baseline: {max_part_b:.0f} /m3  |  AI: {max_part_a:.0f} /m3 (Chuẩn ISO Class 3 <= 1,000)")
    print(f"5. Thời gian Cổng PLC can thiệp:      {fs_mins} phút")
    print("=" * 72)


def display_menu():
    print("\n" + "=" * 76)
    print("      HỆ THỐNG KIỂM THỬ KỊCH BẢN VẬN HÀNH PHÒNG SẠCH BÁN DẪN 300MM")
    print("      (03_SCENARIO_TESTING: 01_BASELINE vs 02_AI_SOLUTION CDCV)")
    print("=" * 76)
    print("  [1] Kịch bản 1: Vận hành Chuẩn 24 Giờ (2 Ca Ngày/Đêm Tiêu chuẩn) [Mặc định]")
    print("  [2] Kịch bản 2: Sự cố Mở Cửa Bảo Dưỡng Buồng Sạch & Xâm Nhập Bụi (11h30)")
    print("  [3] Kịch bản 3: Sóng Nhiệt Mùa Hè Cực Hạn Hsinchu (38.5°C, 90% RH)")
    print("  [4] Kịch bản 4: Đột Biến Hóa Chất AMC (Amoniac NH3 & Dung Môi Track)")
    print("  [5] Kịch bản 5: Chế độ Chờ Cuối Tuần / Bảo Trì Máy Quang Khắc ASML (35 Hz)")
    print("  [6] Master Run: Chạy TẤT CẢ 5 Kịch bản & Tự động mở Báo cáo Tổng hợp PNG")
    print("  [7] Mở tệp Biểu đồ Báo cáo Tổng hợp PNG đã xuất")
    print("  [0] Thoát")
    print("=" * 76)


def main():
    scenarios = get_all_scenarios()

    # Direct launch if passed as CLI argument (e.g., python run_interactive_scenarios.py 1)
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg in scenarios:
            print(f"\n[+] Khởi chạy trực tiếp từ dòng lệnh: {scenarios[arg]['name']}")
            run_live_gui_scenario(scenarios[arg])
            return
        elif arg in ["6", "all"]:
            from scenario_runner import run_all_scenarios_and_export
            from visualize_scenarios import plot_scenarios_report
            run_all_scenarios_and_export()
            plot_scenarios_report(show=True)
            return
        elif arg == "7":
            from visualize_scenarios import plot_scenarios_report
            plot_scenarios_report(show=True)
            return

    while True:
        display_menu()
        try:
            choice = input("\nNhập lựa chọn của bạn (nhấn [1-7] hoặc nhấn phím ENTER để chạy Kịch bản 1): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nĐã thoát chương trình.")
            break

        # If user just presses ENTER without typing anything, default to Scenario 1
        if choice == "":
            choice = "1"

        if choice == "0":
            print("\nĐã thoát chương trình kiểm thử kịch bản. Chúc bạn làm việc hiệu quả!")
            break
        elif choice in ["1", "2", "3", "4", "5"]:
            sc = scenarios[choice]
            run_live_gui_scenario(sc)
            input("\n>>> Nhấn phím ENTER để quay lại Menu chính...")
        elif choice == "6":
            print("\n[+] Đang chạy tự động đối chuẩn toàn bộ 5 kịch bản và mở bảng tổng hợp...")
            from scenario_runner import run_all_scenarios_and_export
            from visualize_scenarios import plot_scenarios_report
            run_all_scenarios_and_export()
            out_png = plot_scenarios_report(show=True)
            print(f"\n[✓] Đã xuất xong biểu đồ tổng hợp: {out_png}")
            input("\n>>> Nhấn phím ENTER để quay lại Menu chính...")
        elif choice == "7":
            png_file = os.path.join(current_dir, "scenario_comparison_report.png")
            if os.path.exists(png_file):
                print(f"\n[+] Đang mở cửa sổ biểu đồ tổng hợp: {png_file}")
                from visualize_scenarios import plot_scenarios_report
                plot_scenarios_report(show=True)
            else:
                print("\nChưa có tệp ảnh báo cáo. Vui lòng chọn [6] để chạy trước!")
            input("\n>>> Nhấn phím ENTER để quay lại Menu chính...")
        else:
            print(f"\n[!] Bạn vừa nhập '{choice}', lựa chọn này không hợp lệ. Vui lòng nhập từ 0 đến 7!")
            input("\n>>> Nhấn phím ENTER để thử lại...")


if __name__ == "__main__":
    main()
