# AI chọn tốc độ MAU/FFU và chốt PLC mô phỏng

**Cảm biến + lịch MES → AI đề xuất tốc độ → PLC kiểm tra → biến tần/quạt**

## Mô hình và một chu kỳ điều khiển

AI dùng hai cây hồi quy học bắt chước, mỗi cây cho một giá trị đặt MAU hoặc FFU. Đầu vào gồm ΔP, hai cỡ hạt, nhiệt độ, RH, NH₃, lưu lượng xả, trạng thái cửa, tải MES, lịch tải và xả năm bước tiếp theo, cùng tốc độ đã thực thi ở chu kỳ trước.

Cặp tốc độ được suy luận một lần mỗi chu kỳ hợp lệ. Hai cây học phần điều chỉnh trong dải tốc độ có thể thực hiện. Cận dưới của MAU được tính trực tiếp từ lịch xả, mức cấp bù và giới hạn ramp. Cận này giúp AI tính đến đợt tăng xả đã biết trước. Thuật toán dò ứng viên của MPC chạy trong khâu tạo dữ liệu và trong nhánh đối chứng. [Cơ sở phương pháp học luật điều khiển](https://arxiv.org/abs/1806.10644) · [Mã AI](../bay1_policy.py).

PLC mô phỏng kiểm tra timestamp của mẫu và lệnh, từ chối gói trùng, quá hạn, thời gian ở tương lai hoặc lệnh tạo trước mẫu. PLC kiểm phạm vi tốc độ và giới hạn thay đổi mỗi phút, rồi dự báo một bước bằng mô hình vật lý với lệnh thực thi. Khi kết nối bị mất, thiếu mô hình, đo lỗi hoặc lệnh bị chặn, PLC yêu cầu giữ sản xuất và áp dụng dự phòng. Phục hồi cần ba lần kiểm tra liên tiếp trên các mẫu mới. [Chốt PLC](../bay1_control.py).

## Chạy và huấn luyện

```powershell
python 02_ai_solution/run_ai_solution.py
python 02_ai_solution/run_interactive_ai_solution.py
python compare_benchmarks.py
```

Mở [dashboard](../cleanroom_visualizer.html) để xem lệnh AI đề xuất và tốc độ quạt thực thi. [Checkpoint](fan_policy.json) được kèm theo và chạy bằng NumPy. Khi huấn luyện lại, trình huấn luyện cần scikit-learn.

```powershell
python 02_ai_solution/train_fan_policy.py
```

Dữ liệu huấn luyện gồm ba kịch bản mô phỏng với các seed riêng và các trạng thái tổng hợp gần giới hạn. Cây học từ các lệnh đạt chốt do MPC vật lý tạo. Checkpoint lưu **6.604 mẫu huấn luyện** và chỉ số sai số trên **4.958 mẫu kiểm định tách riêng**. Kết quả mô phỏng vòng kín và các bài kiểm thử PLC được đánh giá riêng với sai số học bắt chước.

## Đọc kết quả

Benchmark ghi điện quạt, phút ngoài giới hạn, số lệnh AI đề xuất và số lệnh bị chặn. Thời gian tính lệnh trung vị được đo riêng trên các chu kỳ có trạng thái `SAFE`, gồm tính lệnh và kiểm tra PLC trong cùng tiến trình Python. Lịch MES, mô hình phòng, nhiễu và giới hạn được dùng chung trong phép đối chứng. Kết quả phản ánh điều khiển trong mô phỏng Bay 1. [Benchmark đối chứng](../benchmark_comparison.json) · [Năm kịch bản](../03_scenario_testing/scenarios_benchmark_results.json).
