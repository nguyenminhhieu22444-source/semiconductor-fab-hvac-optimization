# Đặc tả mô phỏng Bay 1 300 mm

**Phiên bản** `bay1-simulation-5` · **Ngày cập nhật** 18/11/2026

[bay1_config.json](bay1_config.json) chứa thông số thực thi. Bay 1 là một vùng trộn đều giả định. Cấu hình này kế thừa hình học của mô hình Python đã được dùng trong benchmark trước khi rà soát.

| Hạng mục | Giá trị dùng trong mô phỏng | Cơ sở |
| --- | --- | --- |
| Vùng làm việc | 30 × 18 × 5,22 m, diện tích 540 m², thể tích 2.818,8 m³ | Hình học thiết kế mô phỏng. Sàn nâng, hệ phụ trợ và plenum nằm ngoài thể tích cân bằng. |
| MAU | 10.800 m³/h, 15,5 kW và 50 Hz tại lệnh 100%. Dải 70–100% | Các giá trị định mức là giả định của Bay 1. Đường đồng dạng bậc ba của MAU cần kiểm chứng bằng phép đo khi lọc sạch và bẩn. |
| FFU | 48 × 0,724 m² diện tích lọc hữu hiệu. Vận tốc mặt 0,32–0,52 m/s. Tổng danh định khoảng 65.056 m³/h, tương đương 23,08 ACH tuần hoàn | Diện tích hữu hiệu suy ra từ điểm vận tốc và lưu lượng trong bảng tham chiếu. Công suất nội suy theo các điểm 82,7 / 108,3 / 133,9 W ở 0,32 / 0,42 / 0,52 m/s. Đây là đường ước tính tham chiếu cho một đơn vị, áp dụng đồng nhất cho mô phỏng. |
| Khí tươi | 10.800 m³/h, tương đương 3,83 ACH ở MAU 100% | Tính theo thể tích Bay 1 và chỉ gồm lượng khí tươi qua MAU. |
| Xả công nghệ | Danh định 3.500 / 3.000 / 2.000 m³/h cho acid, dung môi và nhiệt | Tổng danh định 8.500 m³/h. Kịch bản đổi tổng lưu lượng theo lịch. Các nhánh xả được thể hiện ở mức sơ đồ. |
| Chênh áp | Giới hạn thiết kế 15–30 Pa, mục tiêu 19 Pa. Quan hệ rò hai chiều và đường thoát áp giả định bắt đầu tại 19 Pa | Cần hiệu chuẩn tiết diện rò, cửa và đường thoát áp. Với cửa mở và xả bằng khí cấp tối đa, mô hình cho ΔP ổn định bằng 0 Pa. |
| T và RH | Giới hạn 21,5–22,5 °C và 40–45% RH. Điểm đặt 22 °C và 42,5% RH | Giới hạn thiết kế của mô phỏng. Khí rò lấy điều kiện ẩm ngoài trời làm đại diện cho hành lang. |
| Dàn MAU và coil phòng | Lạnh sơ bộ 115 kW, lạnh sâu 155 kW, tái gia nhiệt 50 kW, coil phòng 160 kW tại FFU 100%. Điểm sương cấp mục tiêu 8 °C | Công suất nhiệt giả định. Tải tính theo enthalpy, giới hạn công suất và ẩm ngưng tụ. RH trong phòng được tính từ cân bằng ẩm và nhiệt độ. Sóng nhiệt có thể làm dàn vượt khả năng tách ẩm. |
| Hạt | Hai kênh tích lũy ≥0,1 µm và ≥0,5 µm, lần lượt dùng ngưỡng 1.000 và 35 hạt/m³ | Nguồn trong phòng theo hạt/phút, đổi sang hạt/giây khi tính. Phân bố hạt, hạt ở hành lang, lọc và nồng độ khí cấp là giả định. |
| NH₃ | Ngưỡng thiết kế 10 ppb. Cân bằng nguồn trong phòng, khí tươi, khí xâm nhập, xả và lọc tuần hoàn | 10 ppb là mục tiêu dự án. Hiệu suất lọc và hệ số phát sinh cần kiểm chứng độc lập. Kịch bản tăng NH₃ áp dụng cùng nguồn cho cả baseline và AI. |
| Thiết bị sản xuất | ASML TWINSCAN NXT:2050i và dòng TEL CLEAN TRACK LITHIUS 300 mm | Dùng làm tham chiếu về loại thiết bị. Hồ sơ scanner [JSON](semiconfab_bay1_equipment.json) ở trạng thái nháp. 25/90 kW là giả định tải nội vùng theo lịch, cần số liệu khí phòng, PCW và xả từ hồ sơ lắp đặt. |

[Bảng FFU tham chiếu](https://raw.githubusercontent.com/nguyenminhhieu22444-source/semiconductor-fab-hvac-optimization/main/data/FFU/Table_3_Estimated_FFU_power_consumption_under_different_velocity_conditions.csv), [Phương pháp đo FFU của LBNL](https://eta-publications.lbl.gov/sites/default/files/lbnl-62118.pdf), [Phương trình rò NIST](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.1887r1.pdf), [Nhiệt ẩm ASHRAE](https://handbook.ashrae.org/handbooks/F25/IP/F25_Ch01/F25_Ch01_ip.aspx), [Bảng ngưỡng ISO được ASHRAE trích dẫn](https://handbook.ashrae.org/Handbooks/A23/SI/a23_ch19/a23_ch19_si.aspx), [ASML](https://www.asml.com/en/products/duv-lithography-systems/twinscan-nxt2050i), [TEL](https://www.tel.com/product/lithius.html)

## Phạm vi áp dụng của các nguồn

- Một số số liệu MAU từng gắn nhãn TSMC trùng với Fab 4 ẩn danh, wafer 200 mm, trong khảo sát EPRI/SEMATECH. Dùng các giá trị này làm tham chiếu bối cảnh. Công suất quạt, đường rò và năng lực coil của Bay 1 cần bộ dữ liệu đo riêng. [Khảo sát EPRI TR-113499](https://restservice.epri.com/publicdownload/TR-113499/0/Product)
- CDCV của Zhuang phối hợp khí tươi và khí cấp trong phòng sạch dược phẩm. Bay 1 áp dụng nguyên lý điều tiết theo nhu cầu vào hai lệnh quạt và ghi tải coil theo mô hình. [Zhuang và cộng sự, 2021](https://research.polyu.edu.hk/en/publications/coordinated-demand-controlled-ventilation-strategy-for-energy-eff/)
- ISO 14644-1 xác định cấp sạch qua phép lấy mẫu. Mốc áp suất và NH₃ được chọn cho mô phỏng. VC-D cần vận tốc RMS theo phổ tần. Đánh giá yield cần dữ liệu lot, kích thước die và kết quả kiểm tra sản phẩm. [ISO 14644-1](https://www.iso.org/standard/53394.html), [ISO 14644-4](https://www.iso.org/standard/72379.html), [tiêu chí rung Gordon](https://colingordon.com/wp-content/uploads/2012/07/f3df06a9e162767640cdd8025a54b545.pdf)

## Điều kiện xác nhận tiếp theo

Trước khi dùng kết quả để thiết kế hoặc vận hành fab, cần khảo sát độ kín và cân bằng gió, đo điểm chạy MAU/FFU và dàn lạnh, xác nhận ngưỡng hạt/ẩm trên từng vùng, và thử liên động với thiết bị thực. Trạng thái giữ sản xuất trong phần mềm mô phỏng là tín hiệu yêu cầu. Lịch MES tổng hợp vẫn chạy để quan sát diễn biến sự cố.
