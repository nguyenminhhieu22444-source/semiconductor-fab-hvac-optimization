# 01_baseline: Mô Hình Phòng Sạch Vận Hành Truyền Thống

### 1. Đặc điểm vận hành
- Quạt cấp gió tươi và duy trì áp suất (MAU) chạy cố định ở mức **95%**.
- 48 quạt lọc trần FFU (Fan Filter Unit) chạy cố định ở mức **100%**.
- Không có bộ tối ưu năng lượng AI và không thay đổi tốc độ quạt theo ca làm việc.
- Đây là thực tế phổ biến trong các nhà máy bán dẫn cũ do e ngại nguy cơ nhiễm bụi khi giảm tốc độ quạt.

### 2. Cách chạy mô phỏng
```bash
python run_baseline.py
```

### 3. File đầu ra
- `baseline_results.png`: Đồ thị công suất, chênh áp và nồng độ bụi theo thời gian thực (24 giờ).
- `baseline_kpis.json`: Báo cáo định lượng tổng điện năng tiêu thụ (kWh), công suất trung bình và số phút vi phạm.
