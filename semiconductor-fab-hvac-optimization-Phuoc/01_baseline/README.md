# Baseline cố định

`python 01_baseline/run_baseline.py` chạy ngày đối chuẩn 24 giờ và xuất KPI điện quạt, các kênh môi trường và biểu đồ. MAU 95% và FFU 100% lấy từ [cấu hình Bay 1](../bay1_config.json). Chế độ này mô tả vận hành cố định và ghi nhận các phút ngoài giới hạn.

`python 01_baseline/run_interactive_baseline.py` chạy giao diện desktop. [Dashboard web](../cleanroom_visualizer.html) dùng trace từ benchmark chung.