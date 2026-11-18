# Dự Án Mô Phỏng Phòng Sạch Nhà Máy Bán Dẫn (SemiconFab 300mm Digital Twin)

Dự án được cấu trúc thành 2 module độc lập giúp so sánh trực quan và định lượng giữa chế độ vận hành truyền thống (Baseline) và sau khi áp dụng giải pháp tối ưu AI & Chốt an toàn PLC:

```
semicon_fab_simulation/
├── 01_baseline/                   # Mô hình truyền thống (chạy quạt cố định 95% - 100%)
│   ├── cleanroom_model.py
│   ├── baseline_controller.py
│   ├── run_baseline.py            # Chạy mô phỏng xuất biểu đồ tĩnh
│   ├── run_interactive_baseline.py # Giao diện tương tác trực tiếp trên Desktop
│   ├── baseline_results.png
│   ├── baseline_kpis.json
│   └── README.md
│
├── 02_ai_solution/                # Mô hình ứng dụng giải pháp AI & Chốt an toàn PLC
│   ├── cleanroom_model.py
│   ├── ai_controller.py           # PINN Surrogate + Constrained SLSQP + PLC Gatekeeper
│   ├── run_ai_solution.py         # Chạy mô phỏng giải pháp xuất biểu đồ tĩnh
│   ├── run_interactive_ai_solution.py # Giao diện tương tác trực tiếp giải pháp AI
│   ├── ai_results.png
│   ├── ai_kpis.json
│   └── README.md                  # Tài liệu phân tích chuyên sâu các kỹ thuật áp dụng
│
├── compare_benchmarks.py          # Script chạy cả 2 bản và xuất báo cáo tổng hợp
├── run_interactive_comparison.py  # Chạy 2 màn hình so sánh đối đầu trực tiếp thời gian thực
├── comparison_summary.png         # Đồ thị so sánh 6 khung hình đối đầu trực tiếp
├── benchmark_comparison.json      # Dữ liệu định lượng tiết kiệm năng lượng
├── cleanroom_visualizer.html      # Giao diện Digital Twin Web tương tác trực quan
└── README.md
```

---

### Hướng Dẫn Sử Dụng Nhanh:

1. **Chạy mô phỏng đối đầu trực tiếp trên Desktop (Live GUI):**
   ```bash
   python run_interactive_comparison.py
   ```

2. **Chạy xuất báo cáo so sánh tổng thể và đồ thị:**
   ```bash
   python compare_benchmarks.py
   ```

3. **Mở giao diện Web Visualizer:**
   * Mở file [cleanroom_visualizer.html](file:///c:/Users/admin/OneDrive/Máy tính/semicon_fab_simulation/cleanroom_visualizer.html) trên trình duyệt để theo dõi mô phỏng 2D dòng khí, quạt FFU và thông số môi trường.
