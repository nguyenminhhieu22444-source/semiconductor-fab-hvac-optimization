# Kiểm tra năm kịch bản Bay 1

Chạy từ thư mục dự án.

```powershell
python 03_scenario_testing/scenario_runner.py
python 03_scenario_testing/visualize_scenarios.py
```

Mỗi kịch bản so sánh quạt cố định, điều áp tham chiếu, MPC vật lý và AI phát lệnh trực tiếp trên cùng tải và nhiễu. Kết quả ghi số chu kỳ đổi lệnh, kWh quạt, phút vi phạm, thời gian tính lệnh và số đề xuất AI bị PLC từ chối. Số phút ngoài giới hạn tính theo ΔP, nhiệt độ, RH, hai kênh hạt và NH₃.

| Kịch bản | Mục đích |
| --- | --- |
| Hai ca | Kiểm tra giao ca, tăng xả theo lịch và giảm điện quạt khi tải thấp. |
| Mở cửa và mất kết nối | Kiểm tra mất chênh áp, xâm nhập hạt, giữ sản xuất và phục hồi. |
| Sóng nhiệt | Kiểm tra tải ẩm và giới hạn công suất coil tại 38,5 °C và 90% RH. |
| NH₃ và tăng xả | Kiểm tra nguồn NH₃ tăng 4,5 lần và đủ khí bù khi tăng xả. |
| Cuối tuần | Kiểm tra tải thấp với xả 4.800 m³/h và nguồn NH₃ giảm. |

[Kết quả](scenarios_benchmark_results.json) · [Biểu đồ tổng hợp](scenario_comparison_report.png) · [Cấu hình Bay 1](../bay1_config.json)
