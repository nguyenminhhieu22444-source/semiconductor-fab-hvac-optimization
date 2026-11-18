# 02_AI_SOLUTION: Mô Hình Phòng Sạch Ứng Dụng Giải Pháp AI & Chốt An Toàn PLC

Dự án này hiện thực hóa giải pháp điều khiển thông minh và tối ưu hóa năng lượng cho phòng sạch nhà máy bán dẫn (**SemiconFab 300mm Bay 1 - Lithography & Track**), dựa trên các nghiên cứu khoa học tiên tiến và tiêu chuẩn an toàn công nghiệp quốc tế.

---

## 1. Kiến Trúc Giải Pháp 3 Tầng (3-Tier Architecture)

Sơ đồ khối của giải pháp được cấu trúc theo đúng chu trình điều khiển khép kín:

```
[MES / Production Data]  +  [Cleanroom Sensors]
                   │
                   ▼
  [Khối 1: Data Processing & AI Prediction]  <-- PINN / Physics-Informed Surrogate
                   │
                   ▼
      [Khối 2: AI Energy Optimizer]           <-- Neural-MPC (Constrained SLSQP)
                   │
                   ▼ (Candidate Setpoints)
        [Khối 3: PLC SAFETY CHECK]            <-- Real-time Safety Filter & Interlocks
         /                    \
     (Safe)                 (Unsafe)
       │                        │
       ▼                        ▼
[MAU & FFU Fan Control]   [Fail-Safe Mode (95% Fallback)]
       \                        /
        ───────► [Semiconductor Cleanroom Plant] ◄───────
                            │
               (Continuous Monitoring & KPIs)
```

---

## 2. Chi Tiết Các Kỹ Thuật Đã Ứng Dụng

### Kỹ thuật 1: Data Processing & Physics-Informed Surrogate Model (PINN)
* **Vấn đề giải quyết:** Không thể dùng mô hình vật lý giải tích CFD 3D vì quá chậm (tính bằng giờ), nhưng cũng không thể dùng Deep Learning "hộp đen" thuần túy vì dễ bị ảo giác ngoại suy phi vật lý làm hỏng lô chip wafer.
* **Kỹ thuật ứng dụng:** Mô hình bản sao số nhúng quy luật vật lý (**Physics-Informed Neural Network - PINN**):
  - Nhúng định luật nhiệt động học 1 (First Law of Thermodynamics) để tính toán quán tính nhiệt $C_{\text{thermal}}$.
  - Nhúng phương trình động học dòng khí rò rỉ qua khe hở (Orifice Flow Relation) để dự báo chênh áp $\Delta P$.
  - Nhúng phương trình cân bằng khối lượng hạt bụi với tốc độ lọc HEPA/ULPA 99.999% của 48 quạt FFU.
* **Căn cứ khoa học:** Nghiên cứu *Gargya Gokhale et al. (Applied Energy, 2022 / arXiv:2111.12066)* chứng minh mô hình PINN cần ít dữ liệu huấn luyện, dự báo tầm xa chính xác và suy luận trong thời gian vài mili-giây.

---

### Kỹ thuật 2: Neural Model Predictive Control (Neural-MPC) với Bộ giải SLSQP
* **Vấn đề giải quyết:** Tìm điểm đặt tốc độ quạt $u_{\text{MAU}}, u_{\text{FFU}}$ sao cho tổng điện năng quạt là nhỏ nhất mà 100% không vi phạm tiêu chuẩn ISO Class 3.
* **Kỹ thuật ứng dụng:** Tối ưu hóa phi tuyến có ràng buộc cứng (**Nonlinear Constrained Optimization via SLSQP - Sequential Least Squares Programming**):
  - **Hàm mục tiêu phi tuyến bậc 3:** Tuân theo Định luật đồng dạng quạt (Fan Affinity Law):
    $$\min_{u_{\text{MAU}}, u_{\text{FFU}}} \left[ P_{\text{rated, MAU}} \cdot u_{\text{MAU}}^3 + N_{\text{FFU}} \cdot P_{\text{rated, FFU}} \cdot u_{\text{FFU}}^3 \right]$$
  - **Ràng buộc cứng có biên an toàn (Safety Margin):**
    - $\Delta P_{\text{pred}} \ge 16.5\text{ Pa}$ (ngưỡng quy chuẩn ISO là $15.0\text{ Pa}$).
    - $C_{\text{particle}} \le 650\text{ hạt/m}^3$ (ngưỡng quy chuẩn ISO Class 3 là $1000\text{ hạt/m}^3$).
    - $21.7^\circ\text{C} \le T_{\text{pred}} \le 22.3^\circ\text{C}$ (ổn định quang sai máy quang khắc).
* **Căn cứ khoa học:**
  - *Felix Bünning, John Lygeros et al. (ETH Zürich - arXiv:2011.13227)*: Chứng minh tính khả thi của việc nhúng mạng nơ-ron vào vòng lặp MPC để tối ưu hóa năng lượng làm mát trong khi bảo đảm các ràng buộc an toàn.
  - *Chaoqun Zhuang, Kui Shan, Shengwei Wang (Building and Environment 191, 2021)*: Chứng minh điều phối đồng thời cả gió tươi (MAU) và gió tuần hoàn (FFU) giúp tiết kiệm tới 63.3% điện năng và 89.6% nhiệt sấy bù.

---

### Kỹ thuật 3: PLC Safety Gatekeeper & Bộ lọc an toàn (Safety Filter)
* **Vấn đề giải quyết:** Đảm bảo AI không bao giờ được ra lệnh trực tiếp vượt qua ranh giới an toàn vật lý của nhà máy.
* **Kỹ thuật ứng dụng:** Lớp kiểm tra an toàn tại trạm (Safety Gatekeeper) với 4 cửa ải rà soát độc lập:
  1. **Sensor Integrity Check:** Kiểm tra dải đo cảm biến (phát hiện cảm biến kẹt, đứt dây, nhiễu điện từ EMI).
  2. **Physical Boundary Clamping:** Ràng buộc chặt dải tốc độ quạt khả thi: $u_{\text{MAU}} \in [0.60, 1.00]$ và $u_{\text{FFU}} \in [0.45, 1.00]$.
  3. **Rate-of-Change Limiter:** Khống chế tốc độ tăng/giảm quạt $\le 4\%/\text{phút}$ để chống sốc áp suất buồng khí.
  4. **Positive Pressure Depressurization Interlock:** Nếu $\Delta P < 15.8\text{ Pa}$ mà AI đòi hạ tốc độ quạt MAU $\to$ Phủ quyết lệnh lập tức.
* **Căn cứ khoa học & Chuẩn công nghiệp:**
  - *Kim P. Wabersich & Melanie N. Zeilinger (ETH Zürich - Automatica 2021 / arXiv:1812.05506)*: Chứng minh toán học về bộ lọc an toàn dự báo (Predictive Safety Filter).
  - *Colin Jüni, Philipp Heer et al. (Empa & ETH Zürich - arXiv:2604.16033)*: Chứng minh bộ lọc an toàn thời gian thực giúp triệt tiêu hoàn toàn vi phạm ràng buộc kỹ thuật.
  - *Google DeepMind (2018)*: Kiến trúc kiểm tra 2 tầng độc lập (Two-layer verification) áp dụng cho hạ tầng làm mát thực tế.
  - *Tiêu chuẩn IEC 61508 / IEC 61511*: Nguyên tắc Lớp bảo vệ độc lập (IPL).

---

### Kỹ thuật 4: Fail-Safe Fallback Interlock (Chế độ dự phòng an toàn)
* **Vấn đề giải quyết:** Xử lý sự cố khi AI bị lỗi tính toán, mất tín hiệu mạng, hoặc cảm biến bị hỏng.
* **Kỹ thuật ứng dụng:** Tự động cắt quyền của AI và hoàn trả về chế độ vận hành dự phòng tin cậy (**Validated Fallback Mode**):
  - Setpoint quạt MAU dự phòng: **95%**
  - Setpoint quạt FFU dự phòng: **95%**
  - Trạng thái chuyển đổi diễn ra tức thì trong chu kỳ điều khiển (vài mili-giây), ngăn chặn mọi nguy cơ tụt áp suất làm nhiễm bụi phòng sạch.

---

## 3. Cách Chạy Mô Phỏng

### Cách 1: Chạy mô phỏng tính toán nhanh & xuất báo cáo (Batch Mode)
```bash
python run_ai_solution.py
```
* File xuất ra:
  - `ai_kpis.json`: Báo cáo chỉ số KPI định lượng (kWh, % tiết kiệm, số phút kích hoạt Fail-Safe).
  - `ai_results.png`: Đồ thị công suất, setpoint quạt, trạng thái chốt PLC và áp suất phòng.

### Cách 2: Chạy giao diện tương tác thời gian thực trên Desktop (Live Interactive GUI)
```bash
python run_interactive_ai_solution.py
```
* Hiển thị bảng điều khiển đồ họa động thời gian thực với 4 đồ thị theo dõi trực tiếp các pha điều khiển của AI và thời điểm PLC kích hoạt Fail-Safe khi có sự cố giả lập.

### Cách 3: Chạy so sánh song song với bản Baseline truyền thống
```bash
cd ..
python compare_benchmarks.py           # Xuất báo cáo so sánh tổng hợp
python run_interactive_comparison.py   # Chạy 2 màn hình so sánh đối đầu trực tiếp
```
