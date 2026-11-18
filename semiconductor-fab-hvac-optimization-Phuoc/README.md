# Bay 1 300 mm — điều khiển thông gió theo nhu cầu

Mô phỏng một vùng Lithography & Track với MAU cấp khí tươi, 48 FFU tuần hoàn, xả công nghệ và một cửa nối hành lang. Tải MES và sự cố là các kịch bản tổng hợp. [bay1_config.json](bay1_config.json) là cấu hình dùng chung cho Python, báo cáo và dashboard.

## Luồng AI điều khiển MAU và FFU

MPC vật lý tạo lệnh mẫu khi huấn luyện. Trong mô phỏng, **hai cây hồi quy trực tiếp chọn cặp tốc độ MAU/FFU** mỗi 60 giây ở các chu kỳ đủ điều kiện. PLC quyết định tốc độ thực thi. [Chi tiết huấn luyện và một chu kỳ điều khiển](02_ai_solution/README.md).

```mermaid
flowchart TD
    subgraph Offline["Huấn luyện ngoại tuyến"]
        Scenarios["Kịch bản mô phỏng + thông số Bay 1"] --> MPC["MPC vật lý tìm kiếm lưới<br/>Ưu tiên lệnh ít tốn điện quạt và đạt ràng buộc"]
        MPC -->|Lệnh mẫu MAU và FFU| TrainTrees["Huấn luyện hai cây hồi quy"]
        Physics["Phương trình chênh áp và cân bằng hạt"] --> TrainPINN["Huấn luyện PINN chênh áp và hạt"]
    end

    subgraph Online["Điều khiển Bay 1 trong mô phỏng · Chu kỳ 60 giây"]
        Inputs["Cảm biến phòng sạch + lịch MES"] --> Trees["Hai cây hồi quy<br/>Chọn tốc độ MAU và FFU"]
        Trees -->|Cặp tốc độ đề xuất| PLC{"Chốt PLC mô phỏng<br/>Kiểm tra lệnh và dự báo vật lý một bước"}
        Trees -->|Cùng cặp tốc độ| PINN["PINN dự báo chênh áp và hạt sau 1 phút"]
        PINN -.->|Cảnh báo nếu có| PLC
        Inputs -.->|Số đo và trạng thái kết nối| PLC
        PLC -->|Lệnh đạt kiểm tra| Fans["Biến tần và quạt MAU/FFU"]
        PLC -->|Có lỗi hoặc lệnh bị chặn| Fallback["Tốc độ dự phòng<br/>Yêu cầu tạm dừng sản xuất"]
        Fallback --> Fans
        Fans --> Bay["Mô phỏng phòng sạch Bay 1"]
        Bay --> KPI["Điện quạt và số phút vượt giới hạn"]
        Bay -.->|Số đo cho chu kỳ sau| Inputs
    end

    TrainTrees -.->|Nạp fan_policy.json| Trees
    TrainPINN -.->|Nạp air_pinn_weights.json| PINN
    classDef policy fill:#dcfce7,stroke:#15803d,color:#14532d
    class Trees policy
```

Khi trạng thái phòng và lịch xả cho phép giảm tốc độ, cặp tốc độ do hai cây hồi quy đề xuất có thể giảm điện quạt. Mô phỏng tính điện năng từ tốc độ thực thi sau chốt PLC.

## Chạy mô phỏng

Cần Python và NumPy cho tính toán. Matplotlib dùng cho biểu đồ và giao diện desktop. Pytest dùng cho kiểm tra hồi quy.

```powershell
python compare_benchmarks.py
python 03_scenario_testing/scenario_runner.py
python 03_scenario_testing/visualize_scenarios.py
python -m pytest -q
```

Chạy `python 02_ai_solution/run_interactive_ai_solution.py` để theo dõi tốc độ thực thi, điện quạt và trạng thái PLC trong mô phỏng tương tác.

Mở [cleanroom_visualizer.html](cleanroom_visualizer.html) để xem luồng mô phỏng 24 giờ từ `bay1_traces.js`. Trang hoạt động trực tiếp từ thư mục dự án. `python compare_benchmarks.py --no-plots` cập nhật JSON và dữ liệu web khi chỉ cài NumPy.

Các điểm chạy desktop gồm `run_interactive_comparison.py`, `run_interactive_scenarios.py` và `run_live_environmental_tuning.py`. Hai thư mục `01_baseline` và `02_ai_solution` vẫn có điểm chạy riêng cho từng nhánh.

## Cách điều khiển và đọc KPI

- **Fixed speed** giữ MAU 95% và FFU 100% theo cấu hình đối chuẩn.
- **Pressure reference** điều tiết MAU theo lưu lượng xả và mục tiêu áp suất, giữ FFU ở 100%. Chế độ này cung cấp mốc đối chứng cho phần tối ưu FFU.
- **Điện quạt** là tổng MAU và FFU theo thời gian. **Điện HVAC ước tính** dùng thêm tải lạnh chia cho COP giả định 3,5 và tái gia nhiệt điện. Báo cáo ghi năng lượng tái gia nhiệt riêng theo kWh nhiệt.

Trong benchmark 24 giờ, luồng hai cây hồi quy + PINN + PLC dùng **278,09 kWh điện quạt**, giảm **41,23%** từ mức **473,20 kWh** của chế độ quạt cố định. MPC vật lý và hai cây hồi quy + PLC cũng cho **278,09 kWh**. Cả ba có **20 phút** vượt ít nhất một giới hạn môi trường mô phỏng. Bật PINN cho **0 chu kỳ đổi lệnh** trong benchmark và năm kịch bản chuẩn. [Benchmark 24 giờ](benchmark_comparison.json) · [Năm kịch bản](03_scenario_testing/scenarios_benchmark_results.json)

[Đặc tả Bay 1](SEMICONDUCTOR_FAB_SPECIFICATIONS.md) ghi các giả định mô hình, nguồn và phần cần đo tại hiện trường. [Báo cáo rà soát](HVAC_SYSTEM_AUDIT.md) là mốc trước khi sửa.
