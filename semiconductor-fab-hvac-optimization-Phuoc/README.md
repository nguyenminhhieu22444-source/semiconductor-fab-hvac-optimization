# Bay 1 300 mm — điều khiển thông gió theo nhu cầu

Mô phỏng một vùng Lithography & Track với MAU cấp khí tươi, 48 FFU tuần hoàn, xả công nghệ và một cửa nối hành lang. Tải MES và sự cố là các kịch bản tổng hợp. [bay1_config.json](bay1_config.json) là cấu hình dùng chung cho Python, báo cáo và dashboard.

## Chạy mô phỏng

Cần Python và NumPy cho tính toán. Matplotlib dùng cho biểu đồ và giao diện desktop. Pytest dùng cho kiểm tra hồi quy.

```powershell
python compare_benchmarks.py
python 03_scenario_testing/scenario_runner.py
python 03_scenario_testing/visualize_scenarios.py
python -m pytest -q
```

Mở [cleanroom_visualizer.html](cleanroom_visualizer.html) để xem luồng mô phỏng 24 giờ từ `bay1_traces.js`. Trang hoạt động trực tiếp từ thư mục dự án. `python compare_benchmarks.py --no-plots` cập nhật JSON và dữ liệu web khi chỉ cài NumPy.

Các điểm chạy desktop gồm `run_interactive_comparison.py`, `run_interactive_scenarios.py` và `run_live_environmental_tuning.py`. Hai thư mục `01_baseline` và `02_ai_solution` vẫn có điểm chạy riêng cho từng nhánh.

## Cách điều khiển và đọc KPI

- **Fixed speed** giữ MAU 95% và FFU 100% theo cấu hình đối chuẩn.
- **Pressure reference** điều tiết MAU theo lưu lượng xả và mục tiêu áp suất, giữ FFU ở 100%. Chế độ này cung cấp mốc đối chứng cho phần tối ưu FFU.
- **AI trực tiếp + PLC** dùng cảm biến và lịch MES để tạo cặp tốc độ MAU/FFU sau một lần suy luận. AI học từ lệnh do MPC vật lý tạo lúc huấn luyện. Chốt PLC mô phỏng kiểm tra độ mới, tốc độ và trạng thái môi trường trước khi duyệt lệnh quạt. Khi có lỗi, chốt yêu cầu giữ sản xuất và chạy dự phòng theo giới hạn tốc độ. Phục hồi cần ba mẫu mới liên tiếp qua kiểm tra. [Huấn luyện và kiểm tra lệnh AI](02_ai_solution/README.md).
- **Điện quạt** là tổng MAU và FFU theo thời gian. **Điện HVAC ước tính** dùng thêm tải lạnh chia cho COP giả định 3,5 và tái gia nhiệt điện. Báo cáo ghi năng lượng tái gia nhiệt riêng theo kWh nhiệt.

Trong benchmark 24 giờ, điện quạt là **473,20 kWh** (cố định), **338,74 kWh** (tham chiếu điều áp), **278,09 kWh** (MPC vật lý) và **278,09 kWh** (AI trực tiếp + PLC). Hai nhánh sau chọn cùng lệnh quạt trong benchmark và đều có **20 phút** ngoài giới hạn môi trường mô phỏng. Checkpoint AI được huấn luyện từ dữ liệu mô phỏng. [Benchmark 24 giờ](benchmark_comparison.json) · [Năm kịch bản](03_scenario_testing/scenarios_benchmark_results.json)

[Đặc tả Bay 1](SEMICONDUCTOR_FAB_SPECIFICATIONS.md) ghi các giả định mô hình, nguồn và phần cần đo tại hiện trường. [Báo cáo rà soát](HVAC_SYSTEM_AUDIT.md) là mốc trước khi sửa.
