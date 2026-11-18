# Ghi chú nghiên cứu HVAC phòng sạch

Đối chiếu ngày 18/11/2026 từ `Phương pháp.docx` (văn bản, 14 ảnh và 10 liên kết học thuật) và `zhuang2021.pdf` (14 trang). Các đề xuất trong file Word là nội dung tham khảo cho dự án AI-CDCV Bay 1, với phạm vi bằng chứng ghi dưới đây.

## Zhuang, Shan và Wang (2021) — nền tảng CDCV

- CDCV phối hợp hai quyết định. DCF điều chỉnh lưu lượng khí cấp theo nồng độ hạt và tải lạnh hiện của từng vùng. ADV điều chỉnh xử lý khí tươi qua MAU, chọn giữa chế độ tách một phần (PD) và chế độ khí tươi riêng (DV) theo tải ẩn và năng lượng, với lưu lượng khí tươi tối thiểu để duy trì áp dương. Chi tiết ở §3.1 và Bảng 2. [Bài báo tại PolyU](https://research.polyu.edu.hk/en/publications/coordinated-demand-controlled-ventilation-strategy-for-energy-eff/)
- Bảng 4 so sánh điện năng HVAC một năm cho phòng sạch dược phẩm đa vùng tại Hồng Kông. Mô hình EnergyPlus được hiệu chuẩn bằng tải lạnh đo tại công trình. Bài báo giả định phát sinh hạt theo số người, đồng thời lưu ý ảnh hưởng của quy trình sản xuất, chênh áp và bất định đo lường. Các số liệu dùng để đối chiếu phương pháp. Thiết bị, tải và điều kiện vận hành thực tế của Bay 1 cần dữ liệu riêng. [Bài báo tại PolyU](https://research.polyu.edu.hk/en/publications/coordinated-demand-controlled-ventilation-strategy-for-energy-eff/)

| Phương án trong Bảng 4 | Điện năm | Tiết kiệm so với cấu hình gốc |
| --- | ---: | ---: |
| Gốc, khí tươi và khí cấp cố định | 371,2 MWh | — |
| Chỉ tối ưu khí tươi | 307,1 MWh | 17,3% |
| Chỉ tối ưu khí cấp | 177,1 MWh | 52,3% |
| CDCV, tối ưu cả hai | 136,1 MWh | 63,3% |

Năng lượng tái gia nhiệt của AHU giảm từ 128,3 xuống 13,4 MWh, tương ứng 89,6% so với cấu hình gốc. Phạm vi điện trong Bảng 4 gồm làm lạnh, tái gia nhiệt và quạt, nên cần dùng cùng biên tính năng lượng khi so sánh với kết quả mô phỏng Bay 1. [Bài báo tại PolyU](https://research.polyu.edu.hk/en/publications/coordinated-demand-controlled-ventilation-strategy-for-energy-eff/)

## Nguồn về thông gió, chênh áp và hạt

| Chủ đề | Kết quả đã đối chiếu | Nguồn |
| --- | --- | --- |
| DCF và giảm lưu lượng khi phòng trống | Loomans và cộng sự (2020) thí nghiệm giảm số lần trao đổi khí và chênh áp trong phòng sạch mô phỏng khi phòng trống. Kết luận về tính khả thi phụ thuộc vào giả định nhân sự là nguồn ô nhiễm chính và điều kiện thí nghiệm. | [Bản toàn văn TU Eindhoven](https://pure.tue.nl/ws/files/149381193/1_s2.0_S0360132320302201_main.pdf) |
| Thiết kế HVAC tối ưu | Porowski và Jakubiak (2022) xét ảnh hưởng của cấp sạch, tải lạnh, tỷ lệ khí ngoài, khí hậu và thu hồi nhiệt đến năng lượng sơ cấp hằng năm. Phạm vi cấp sạch của nghiên cứu là ISO 5–8, còn Bay 1 dùng mục tiêu ISO Class 3 theo README dự án. | [Bài báo trên Energies](https://www.mdpi.com/1996-1073/15/1/313) |
| Rò rỉ qua khe hở | Xu trình bày quan hệ giữa chênh áp, gió bên ngoài và xâm nhập qua khe cửa hoặc cửa sổ. Đây là cơ sở để xét rò rỉ khi cửa đóng và ảnh hưởng của áp suất ở không gian liền kề. | [Mục về rò rỉ qua khe hở](https://pmc.ncbi.nlm.nih.gov/articles/PMC7498934/#Sec55), [chương sách tại Springer](https://link.springer.com/chapter/10.1007/978-3-642-39374-7_8) |
| Mở cửa và người đi qua | Knudsen và cộng sự (2019) đo khí đánh dấu trong 13 kịch bản tại phòng sạch mô phỏng kích thước thực. Vận tốc khí qua cửa, thời gian mở và chênh nhiệt giữa phòng đệm và phòng sạch ảnh hưởng lượng khí xâm nhập. Nghiên cứu cũng thử chuyển động của hình nhân qua cửa. | [Bản xuất bản tại DTU](https://backend.orbit.dtu.dk/ws/files/202849780/Lind_Knudsen_2019_IOP_Conf._Ser._Mater._Sci._Eng._609_032049.pdf) |
| Nhiễu động và xâm nhập hạt | Raji và cộng sự (2026) dùng CFD, mô hình hạt rời rạc và lưới động để mô phỏng cửa bản lề nối phòng sạch với phòng đệm. Tốc độ và hướng quay của cửa ảnh hưởng đến vận chuyển hạt trong cấu hình mô phỏng. | [Tóm tắt của nhà xuất bản](https://www.sciencedirect.com/science/article/pii/S2590123025049655) |
| Bố trí FFU | Yao và cộng sự (2025) mô phỏng rò HCl khi bảo trì thiết bị bán dẫn. Bố trí và tỷ lệ phủ FFU làm thay đổi phân bố dòng khí ngay cả khi giữ nguyên ACH. Kết quả về mảng FFU ngang với độ phủ 30% thuộc cấu hình rò HCl được mô phỏng. | [Trang bài báo của SKKU](https://pure.skku.edu/en/publications/a-numerical-study-on-effective-arrangement-of-fan-filter-units-in/) |

## Nguồn về dự báo, tối ưu và chốt an toàn

| Chủ đề | Kết quả đã đối chiếu | Nguồn |
| --- | --- | --- |
| PINN dự báo nhiệt | Gokhale và cộng sự nhúng động học nhiệt vào mô hình học. Trong các thử nghiệm nhiệt độ tòa nhà, các kiến trúc dùng dữ liệu huấn luyện hiệu quả hơn và dự báo tốt hơn ở kỳ hạn dài so với mạng thông thường. Độ chính xác đối với hạt và chênh áp, hành vi khi ngoại suy và thời gian suy luận cần được đánh giá trên mô hình Bay 1. | [arXiv:2111.12066](https://arxiv.org/abs/2111.12066) |
| Mạng nơ-ron trong MPC | Bünning và cộng sự ràng buộc cấu trúc và trọng số của mạng lồi theo đầu vào để giữ tính lồi qua nhiều bước dự báo. Họ thử nghiệm MPC trong hai đợt làm mát căn hộ. Khả năng giải đúng chu kỳ điều khiển của bài toán MAU–FFU phụ thuộc vào mô hình, ràng buộc, bộ giải và phần cứng của bài toán đó. | [arXiv:2011.13227](https://arxiv.org/abs/2011.13227) |
| MPC đa biến cho chênh áp | Jeremić và Rakić (2025) thử trên hệ phòng sạch thực với van gió cấp/xả, điều khiển lưu lượng và chênh áp. Kiến trúc dùng MPC theo phòng và PID vòng ngoài cho áp suất ống gió. Bài báo cung cấp bằng chứng cho điều khiển đa biến trong hệ được thử nghiệm. | [Bài báo trên Electronics](https://www.mdpi.com/2079-9292/14/16/3296) |
| Bộ lọc an toàn thích ứng | Preprint của Jüni và cộng sự mô phỏng điều khiển sưởi tòa nhà. Bộ lọc đảm bảo tuân thủ các yêu cầu điều chỉnh phụ tải trong mô phỏng, còn vi phạm ngưỡng nhiệt độ tiện nghi vẫn xuất hiện. Mệnh đề “0% vi phạm tuyệt đối” trong Word vượt phạm vi kết quả của bài. Tích hợp PLC và chế độ dự phòng của Bay 1 là đề xuất triển khai trong tài liệu dự án. | [Preprint arXiv, §5 và Bảng 1](https://arxiv.org/pdf/2604.16033) |

Các nguồn trên gợi ý cách diễn giải kiến trúc trong Word. PINN dự báo trạng thái, MPC đề xuất lệnh MAU/FFU theo ràng buộc mô hình, và chốt an toàn PLC quyết định cho phép lệnh hoặc chuyển sang chế độ dự phòng. Các ràng buộc mô phỏng, thông số thiết bị và kết quả vận hành của Bay 1 cần gắn với dữ liệu hoặc kịch bản tương ứng của dự án.

ScienceDirect chặn một số lần mở trực tiếp và IOP không tải được. Các nguồn tương ứng được đối chiếu qua bản toàn văn của trường, tóm tắt của nhà xuất bản hoặc kho của trường. Trong danh mục tham khảo của PDF, liên kết cũ đến cơ sở dữ liệu WMO trả về 404. Đài Thiên văn Hồng Kông có cổng thông tin khí hậu riêng. Trang IVT về nhân sự phòng sạch chưa tải được, nhưng Tim Sandle có đăng bản sao bài viết. [Thông tin khí hậu Hồng Kông](https://www.weather.gov.hk/en/cis/climat.htm), [bản do Sandle đăng](https://www.researchgate.net/publication/299507535_People_in_Cleanrooms_Understanding_and_Monitoring_the_Personnel_Factor)
