/**
 * BURONIX INTERACTIVE DIGITAL TWIN ANIMATOR (CANVAS 2D)
 * 60 FPS Fluid Physical Simulation of MAU + Cleanroom Bay 1
 * Inspired by Buronix.com demo aesthetic
 */

class BuronixAnimator {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    
    // Virtual resolution
    this.width = 1100;
    this.height = 540;

    // Component Bounding Boxes for Click/Hover Detection
    this.components = {
      intake_damper: { x: 30, y: 170, w: 45, h: 100, name: "Cửa Gió Tươi & Damper A", type: "MAU_DAMPER" },
      filter_g4:     { x: 85, y: 170, w: 30, h: 100, name: "Lọc Thô G4 (Pre-Filter)", type: "MAU_FILTER_G4" },
      coil_precool:  { x: 125, y: 170, w: 35, h: 100, name: "Dàn Làm Lạnh Sơ Cấp (12°C CW)", type: "MAU_PRECOOL" },
      coil_recool:   { x: 170, y: 170, w: 35, h: 100, name: "Dàn Lạnh Sâu & Tách Ẩm (6°C CW)", type: "MAU_RECOOL" },
      coil_reheat:   { x: 215, y: 170, w: 35, h: 100, name: "Dàn Sấy Nóng Tái Nhiệt (Reheat)", type: "MAU_REHEAT" },
      humidifier:    { x: 260, y: 170, w: 35, h: 100, name: "Cụm Phun Ẩm Siêu Âm", type: "MAU_HUMIDIFIER" },
      mau_fan:       { x: 305, y: 160, w: 60, h: 120, name: "Quạt Cấp Khí Tươi Biến Tần VFD", type: "MAU_FAN" },
      filter_subhepa:{ x: 375, y: 170, w: 35, h: 100, name: "Lọc Tinh F8 & Cận HEPA H11", type: "MAU_FINAL_FILTER" },
      supply_duct:   { x: 415, y: 60, w: 100, h: 130, name: "Đường Ống Gió Cấp Trần (Supply Duct)", type: "DUCT" },
      ceiling_plenum:{ x: 520, y: 40, w: 530, h: 60, name: "Trần Kỹ Thuật (Ceiling Plenum)", type: "PLENUM" },
      ffu_grid:      { x: 530, y: 100, w: 510, h: 40, name: "Lưới 48 Quạt Trần FFU & Màng ULPA", type: "FFU_GRID" },
      cleanroom_bay: { x: 520, y: 140, w: 530, h: 250, name: "Phòng Sạch Bay 1 (ISO Class 3)", type: "CLEANROOM" },
      asml_scanner:  { x: 710, y: 240, w: 150, h: 130, name: "Máy Quang Khắc ASML Twinscan DUV", type: "ASML_SCANNER" },
      wafer_track:   { x: 550, y: 260, w: 120, h: 110, name: "Máy Phủ & Hiện Cản Quang Track", type: "TRACK" },
      airlock_door:  { x: 1000, y: 250, w: 35, h: 120, name: "Cửa Airlock Khí Chênh Áp", type: "AIRLOCK" },
      floor_plenum:  { x: 520, y: 390, w: 530, h: 40, name: "Sàn Nâng Đục Lỗ (Raised Floor)", type: "RAISED_FLOOR" },
      subfab_exhaust:{ x: 520, y: 430, w: 530, h: 80, name: "Hệ Thống Xả Khí Độc Subfab", type: "EXHAUST" },
      dcc_riser:     { x: 440, y: 220, w: 45, h: 200, name: "Đường Hồi Gió & Dàn Lạnh Khô DCC", type: "DCC_RISER" }
    };

    this.hoveredComponent = null;
    this.selectedComponent = 'mau_fan';

    // Particle Animation Loop System
    this.particles = [];
    this.initParticles();

    // Condensation droplets in dehumidifier
    this.droplets = [];
    for (let i = 0; i < 15; i++) {
      this.droplets.push({
        x: 175 + Math.random() * 25,
        y: 180 + Math.random() * 70,
        speed: 1.0 + Math.random() * 2.0,
        len: 3 + Math.random() * 4
      });
    }

    // Mist particles for humidifier
    this.mist = [];
    for (let i = 0; i < 25; i++) {
      this.mist.push({
        x: 265 + Math.random() * 25,
        y: 180 + Math.random() * 80,
        vx: 0.5 + Math.random() * 1.5,
        vy: (Math.random() - 0.5) * 1.0,
        alpha: 0.2 + Math.random() * 0.6
      });
    }

    // Fan rotation angle
    this.fanAngle = 0;
    this.ffuFanAngle = 0;

    // Mouse Listeners
    this.initEventListeners();

    // Animation runner
    this.running = true;
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initParticles() {
    this.particles = [];
    const count = 180;
    for (let i = 0; i < count; i++) {
      this.particles.push({
        stage: Math.floor(Math.random() * 4), // 0: MAU, 1: Duct/Plenum, 2: Cleanroom, 3: Return/Exhaust
        progress: Math.random(),
        speed: 0.003 + Math.random() * 0.004,
        offset: (Math.random() - 0.5) * 40
      });
    }
  }

  initEventListeners() {
    const handleMove = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.width / rect.width;
      const scaleY = this.height / rect.height;
      const mx = (e.clientX - rect.left) * scaleX;
      const my = (e.clientY - rect.top) * scaleY;

      let found = null;
      for (const [key, box] of Object.entries(this.components)) {
        if (mx >= box.x && mx <= box.x + box.w && my >= box.y && my <= box.y + box.h) {
          found = key;
          break;
        }
      }
      this.hoveredComponent = found;
      this.canvas.style.cursor = found ? 'pointer' : 'default';
    };

    const handleClick = (e) => {
      if (this.hoveredComponent) {
        this.selectedComponent = this.hoveredComponent;
        if (window.onComponentSelect) {
          window.onComponentSelect(this.components[this.selectedComponent]);
        }
      }
    };

    this.canvas.addEventListener('mousemove', handleMove);
    this.canvas.addEventListener('click', handleClick);
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = this.width;
    this.canvas.height = this.height;
  }

  animate() {
    if (!this.running) return;

    this.ctx.clearRect(0, 0, this.width, this.height);

    const plant = window.CLEANROOM_PLANT || { u_mau: 0.90, u_ffu: 0.90, dp: 18.0, temp: 22.0 };
    const speedFactor = plant.u_mau;

    // Rotate fans
    this.fanAngle += 0.15 * (plant.u_mau / 0.90);
    this.ffuFanAngle += 0.20 * (plant.u_ffu / 0.90);

    // 1. Draw Architectural Structure & Chambers
    this.drawBackgroundGrid();
    this.drawSubfabExhaust();
    this.drawCleanroomChamber();
    this.drawCeilingPlenum();
    this.drawMauChamber(plant);
    this.drawDuctwork();

    // 2. Draw Equipment & Machinery
    this.drawAsmlScanner();
    this.drawWaferTrack();
    this.drawFfuGrid(plant);
    this.drawMauInternalComponents(plant);

    // 3. Draw Dynamic Particle Streams & Airflow
    this.drawAirflowParticles(speedFactor);
    this.drawCondensationDroplets();
    this.drawHumidifierMist();

    // 4. Draw Overlays & Highlights
    this.drawComponentHighlights();

    requestAnimationFrame(this.animate);
  }

  drawBackgroundGrid() {
    const ctx = this.ctx;
    ctx.strokeStyle = "rgba(30, 41, 59, 0.25)";
    ctx.lineWidth = 1;
    for (let x = 0; x < this.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, this.height);
      ctx.stroke();
    }
    for (let y = 0; y < this.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(this.width, y);
      ctx.stroke();
    }
  }

  drawMauChamber(plant) {
    const ctx = this.ctx;
    const x = 20, y = 150, w = 400, h = 140;

    // Outer Casing
    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 10);
    ctx.fill();
    ctx.stroke();

    // Header label
    ctx.fillStyle = "#38bdf8";
    ctx.font = "bold 11px JetBrains Mono, monospace";
    ctx.fillText("🌬️ MAKE-UP AIR UNIT (MAU) — DUAL-COIL & REHEAT", x + 12, y - 8);

    // Flow arrow header
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px Inter, sans-serif";
    ctx.fillText("Khí tươi ngoài trời 32°C ➔ Xử lý nhiệt ẩm ➔ Gió cấp buồng 20.99°C", x + 12, y + h + 18);
  }

  drawMauInternalComponents(plant) {
    const ctx = this.ctx;

    // 1. Damper A (Rotating blade)
    const dBox = this.components.intake_damper;
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 3;
    const angle = (1.0 - plant.u_mau) * 0.7; // angle rotates with opening
    ctx.beginPath();
    ctx.moveTo(dBox.x + 10, dBox.y + 15);
    ctx.lineTo(dBox.x + 35, dBox.y + 35 + angle * 30);
    ctx.moveTo(dBox.x + 10, dBox.y + 55);
    ctx.lineTo(dBox.x + 35, dBox.y + 75 + angle * 30);
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px JetBrains Mono, monospace";
    ctx.fillText("DAMPER", dBox.x, dBox.y + 115);

    // 2. Filter G4 (Primary)
    const fBox = this.components.filter_g4;
    ctx.fillStyle = "rgba(100, 116, 139, 0.3)";
    ctx.fillRect(fBox.x, fBox.y + 10, fBox.w, fBox.h - 20);
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 1;
    for (let py = fBox.y + 15; py < fBox.y + fBox.h - 15; py += 8) {
      ctx.beginPath();
      ctx.moveTo(fBox.x, py);
      ctx.lineTo(fBox.x + fBox.w, py + 4);
      ctx.stroke();
    }
    ctx.fillText("G4", fBox.x + 8, fBox.y + 115);

    // 3. Pre-Cooling Coil (12°C CW)
    const pcBox = this.components.coil_precool;
    const pcGrad = ctx.createLinearGradient(pcBox.x, 0, pcBox.x + pcBox.w, 0);
    pcGrad.addColorStop(0, "rgba(56, 189, 248, 0.6)");
    pcGrad.addColorStop(1, "rgba(2, 132, 199, 0.7)");
    ctx.fillStyle = pcGrad;
    ctx.fillRect(pcBox.x, pcBox.y + 10, pcBox.w, pcBox.h - 20);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    for (let py = pcBox.y + 15; py < pcBox.y + pcBox.h - 15; py += 12) {
      ctx.strokeRect(pcBox.x + 4, py, pcBox.w - 8, 8);
    }
    ctx.fillText("PRECOOL", pcBox.x - 4, pcBox.y + 115);

    // 4. Deep Recool / Dehumidification Coil (6°C CW)
    const rcBox = this.components.coil_recool;
    const rcGrad = ctx.createLinearGradient(rcBox.x, 0, rcBox.x + rcBox.w, 0);
    rcGrad.addColorStop(0, "rgba(2, 132, 199, 0.7)");
    rcGrad.addColorStop(1, "rgba(14, 165, 233, 0.9)");
    ctx.fillStyle = rcGrad;
    ctx.fillRect(rcBox.x, rcBox.y + 10, rcBox.w, rcBox.h - 20);
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 1.5;
    for (let py = rcBox.y + 15; py < rcBox.y + rcBox.h - 15; py += 10) {
      ctx.strokeRect(rcBox.x + 4, py, rcBox.w - 8, 6);
    }
    ctx.fillText("RECOOL", rcBox.x - 2, rcBox.y + 115);

    // 5. Reheat Coil (Reheat)
    const rhBox = this.components.coil_reheat;
    const rhGrad = ctx.createLinearGradient(rhBox.x, 0, rhBox.x + rhBox.w, 0);
    rhGrad.addColorStop(0, "rgba(239, 68, 68, 0.6)");
    rhGrad.addColorStop(1, "rgba(249, 115, 22, 0.7)");
    ctx.fillStyle = rhGrad;
    ctx.fillRect(rhBox.x, rhBox.y + 10, rhBox.w, rhBox.h - 20);
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let py = rhBox.y + 15; py < rhBox.y + rhBox.h - 15; py += 14) {
      ctx.moveTo(rhBox.x + 4, py);
      ctx.lineTo(rhBox.x + rhBox.w - 4, py + 7);
    }
    ctx.stroke();
    ctx.fillText("REHEAT", rhBox.x - 2, rhBox.y + 115);

    // 6. Humidifier
    const hBox = this.components.humidifier;
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(hBox.x + 6, hBox.y + 15, hBox.w - 12, hBox.h - 30);
    ctx.fillText("HUMID", hBox.x + 2, hBox.y + 115);

    // 7. MAU Supply Fan
    const fanBox = this.components.mau_fan;
    const cx = fanBox.x + fanBox.w / 2;
    const cy = fanBox.y + fanBox.h / 2;
    const radius = 32;

    // Fan Casing
    ctx.fillStyle = "#1e293b";
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Fan Blades (Spinning)
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.fanAngle);
    for (let b = 0; b < 6; b++) {
      ctx.rotate(Math.PI / 3);
      ctx.fillStyle = "rgba(0, 229, 255, 0.75)";
      ctx.beginPath();
      ctx.ellipse(14, 0, 12, 4, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    // Fan Hub
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(0, 0, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.fillStyle = "#00e5ff";
    ctx.font = "bold 9px JetBrains Mono, monospace";
    const vfdHz = 35.0 + (plant.u_mau - 0.70) * ((50.0 - 35.0) / 0.30);
    ctx.fillText(`${vfdHz.toFixed(1)} Hz`, fanBox.x + 12, fanBox.y + fanBox.h + 5);

    // 8. Sub-HEPA / Final Filter
    const sfBox = this.components.filter_subhepa;
    ctx.fillStyle = "rgba(0, 255, 136, 0.2)";
    ctx.fillRect(sfBox.x, sfBox.y + 10, sfBox.w, sfBox.h - 20);
    ctx.strokeStyle = "#00ff88";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(sfBox.x, sfBox.y + 10, sfBox.w, sfBox.h - 20);
    ctx.fillStyle = "#94a3b8";
    ctx.fillText("F8/H11", sfBox.x - 2, sfBox.y + 115);
  }

  drawDuctwork() {
    const ctx = this.ctx;
    // Supply Duct from MAU to Ceiling Plenum
    ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
    ctx.lineWidth = 22;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(410, 220);
    ctx.lineTo(460, 220);
    ctx.lineTo(460, 70);
    ctx.lineTo(520, 70);
    ctx.stroke();

    // Inner line
    ctx.strokeStyle = "rgba(0, 229, 255, 0.8)";
    ctx.lineWidth = 2;
    ctx.stroke();

    // DCC Return Air Riser (from Subfab up to Plenum)
    ctx.strokeStyle = "rgba(71, 85, 105, 0.4)";
    ctx.lineWidth = 20;
    ctx.beginPath();
    ctx.moveTo(520, 410);
    ctx.lineTo(460, 410);
    ctx.lineTo(460, 260);
    ctx.stroke();

    // DCC Coil Box
    ctx.fillStyle = "rgba(30, 41, 59, 0.9)";
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(440, 270, 40, 60);
    ctx.fillStyle = "#38bdf8";
    ctx.font = "8px JetBrains Mono, monospace";
    ctx.fillText("DCC", 450, 305);
  }

  drawCeilingPlenum() {
    const ctx = this.ctx;
    const box = this.components.ceiling_plenum;

    // Plenum Box
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
    ctx.lineWidth = 1.5;
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.strokeRect(box.x, box.y, box.w, box.h);

    ctx.fillStyle = "#38bdf8";
    ctx.font = "bold 10px JetBrains Mono, monospace";
    ctx.fillText("▲ CEILING SUPPLY PLENUM (ÁP LỰC DƯƠNG TĨNH)", box.x + 14, box.y + 20);
  }

  drawFfuGrid(plant) {
    const ctx = this.ctx;
    const box = this.components.ffu_grid;

    // 12 FFU modules shown in section
    const numUnits = 12;
    const unitW = box.w / numUnits;

    for (let i = 0; i < numUnits; i++) {
      const ux = box.x + i * unitW;
      // FFU Box
      ctx.fillStyle = "rgba(30, 41, 59, 0.95)";
      ctx.strokeStyle = "rgba(0, 255, 136, 0.4)";
      ctx.lineWidth = 1;
      ctx.fillRect(ux + 2, box.y, unitW - 4, box.h);
      ctx.strokeRect(ux + 2, box.y, unitW - 4, box.h);

      // Mini fan impeller spinning
      const cx = ux + unitW / 2;
      const cy = box.y + 14;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(this.ffuFanAngle + i * 0.5);
      ctx.fillStyle = "#00ff88";
      ctx.fillRect(-6, -1.5, 12, 3);
      ctx.fillRect(-1.5, -6, 3, 12);
      ctx.restore();

      // HEPA/ULPA Filter Membrane (Green line)
      ctx.fillStyle = "rgba(0, 255, 136, 0.85)";
      ctx.fillRect(ux + 4, box.y + box.h - 5, unitW - 8, 3);
    }

    ctx.fillStyle = "#00ff88";
    ctx.font = "bold 9px JetBrains Mono, monospace";
    ctx.fillText(`LƯỚI 48 FFU: ${(plant.u_ffu * 100).toFixed(0)}% TỐC ĐỘ (0.41 m/s Laminar)`, box.x + 10, box.y + box.h - 8);
  }

  drawCleanroomChamber() {
    const ctx = this.ctx;
    const box = this.components.cleanroom_bay;

    // Cleanroom Room
    const grad = ctx.createLinearGradient(0, box.y, 0, box.y + box.h);
    grad.addColorStop(0, "rgba(13, 22, 43, 0.65)");
    grad.addColorStop(1, "rgba(6, 9, 19, 0.85)");
    ctx.fillStyle = grad;
    ctx.fillRect(box.x, box.y, box.w, box.h);

    ctx.strokeStyle = "rgba(0, 229, 255, 0.4)";
    ctx.lineWidth = 2;
    ctx.strokeRect(box.x, box.y, box.w, box.h);

    // Title & Standard
    ctx.fillStyle = "#fff";
    ctx.font = "bold 13px Inter, sans-serif";
    ctx.fillText("BAY 1: PHOTOLITHOGRAPHY & TRACK", box.x + 16, box.y + 24);

    ctx.fillStyle = "#00e5ff";
    ctx.font = "10px JetBrains Mono, monospace";
    ctx.fillText("ISO 14644-1:2015 Class 3 | Thể tích 2,818.8 m³ | ΔP ≥ +15.0 Pa", box.x + 16, box.y + 40);

    // Floor Grating (Perforated raised floor)
    const flBox = this.components.floor_plenum;
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(flBox.x, flBox.y, flBox.w, flBox.h);
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 1;
    for (let px = flBox.x + 4; px < flBox.x + flBox.w; px += 8) {
      ctx.strokeRect(px, flBox.y + 4, 4, flBox.h - 8);
    }
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px JetBrains Mono, monospace";
    ctx.fillText("SÀN NÂNG ĐỤC LỖ (PERFORATED ACCESS FLOOR) ➔ THU HỒI KHÍ VỀ SUBFAB", flBox.x + 14, flBox.y + 24);
  }

  drawAsmlScanner() {
    const ctx = this.ctx;
    const box = this.components.asml_scanner;

    // Machine base
    ctx.fillStyle = "rgba(30, 41, 59, 0.95)";
    ctx.strokeStyle = "rgba(0, 229, 255, 0.6)";
    ctx.lineWidth = 2;
    ctx.strokeRect(box.x, box.y, box.w, box.h);

    // Lens column
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(box.x + 40, box.y + 15, 70, 75);
    ctx.strokeStyle = "#38bdf8";
    ctx.strokeRect(box.x + 40, box.y + 15, 70, 75);

    // Laser exposure beam (Pulsing blue light)
    ctx.fillStyle = "rgba(0, 229, 255, 0.35)";
    ctx.beginPath();
    ctx.moveTo(box.x + 75, box.y + 20);
    ctx.lineTo(box.x + 55, box.y + 85);
    ctx.lineTo(box.x + 95, box.y + 85);
    ctx.closePath();
    ctx.fill();

    // Wafer Stage
    ctx.fillStyle = "#e2e8f0";
    ctx.beginPath();
    ctx.ellipse(box.x + 75, box.y + 95, 26, 7, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#fff";
    ctx.font = "bold 10px Inter, sans-serif";
    ctx.fillText("ASML DUV SCANNER", box.x + 22, box.y + 115);

    ctx.fillStyle = "#94a3b8";
    ctx.font = "8px JetBrains Mono, monospace";
    ctx.fillText("Tải nhiệt: 90 kW | VC-D: 0.047 cm/s²", box.x + 8, box.y + box.h - 3);
  }

  drawWaferTrack() {
    const ctx = this.ctx;
    const box = this.components.wafer_track;

    ctx.fillStyle = "rgba(30, 41, 59, 0.9)";
    ctx.strokeStyle = "rgba(168, 85, 247, 0.5)";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(box.x, box.y, box.w, box.h);

    ctx.fillStyle = "#d8b4fe";
    ctx.font = "bold 9px Inter, sans-serif";
    ctx.fillText("TRACK COATER/DEV", box.x + 12, box.y + 20);

    ctx.fillStyle = "#94a3b8";
    ctx.font = "8px JetBrains Mono, monospace";
    ctx.fillText("Hút khí dung môi VOC", box.x + 12, box.y + 35);
  }

  drawSubfabExhaust() {
    const ctx = this.ctx;
    const box = this.components.subfab_exhaust;

    // Subfab Background
    ctx.fillStyle = "rgba(11, 17, 32, 0.95)";
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.strokeStyle = "#334155";
    ctx.strokeRect(box.x, box.y, box.w, box.h);

    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 9px JetBrains Mono, monospace";
    ctx.fillText("▼ SUBFAB SEGREGATED EXHAUST (3 ĐƯỜNG XẢ KHÍ ĐỘC PHÂN LUỒNG)", box.x + 14, box.y + 16);

    // 3 Pipe paths
    // Acid (Yellow)
    ctx.fillStyle = "rgba(234, 179, 8, 0.2)";
    ctx.strokeStyle = "#eab308";
    ctx.strokeRect(box.x + 20, box.y + 28, 140, 22);
    ctx.fillStyle = "#eab308";
    ctx.fillText("ACID: 3,500 m³/h", box.x + 28, box.y + 43);

    // Solvent VOC (Purple)
    ctx.fillStyle = "rgba(168, 85, 247, 0.2)";
    ctx.strokeStyle = "#a855f7";
    ctx.strokeRect(box.x + 180, box.y + 28, 150, 22);
    ctx.fillStyle = "#d8b4fe";
    ctx.fillText("SOLVENT VOC: 3,000 m³/h", box.x + 188, box.y + 43);

    // General Heat (Orange)
    ctx.fillStyle = "rgba(249, 115, 22, 0.2)";
    ctx.strokeStyle = "#f97316";
    ctx.strokeRect(box.x + 350, box.y + 28, 150, 22);
    ctx.fillStyle = "#fdba74";
    ctx.fillText("HEAT EXH: 2,000 m³/h", box.x + 360, box.y + 43);
  }

  drawAirflowParticles(speedFactor) {
    const ctx = this.ctx;

    this.particles.forEach((p) => {
      p.progress += p.speed * speedFactor * 1.5;
      if (p.progress > 1.0) {
        p.progress = 0.0;
        p.stage = (p.stage + 1) % 4;
      }

      let px = 0, py = 0, pColor = "#00e5ff";

      if (p.stage === 0) {
        // Stage 0: Inside MAU Chamber (x: 30 -> 400, y: 220)
        px = 30 + p.progress * 370;
        py = 220 + p.offset * 0.7;
        pColor = p.progress < 0.3 ? "#f59e0b" : (p.progress < 0.6 ? "#00e5ff" : "#00ff88");
      } else if (p.stage === 1) {
        // Stage 1: Duct & Ceiling Plenum (x: 420 -> 1000)
        if (p.progress < 0.3) {
          px = 420 + p.progress * 100;
          py = 220 - (p.progress / 0.3) * 150;
        } else {
          px = 520 + ((p.progress - 0.3) / 0.7) * 480;
          py = 70 + p.offset * 0.4;
        }
        pColor = "#00e5ff";
      } else if (p.stage === 2) {
        // Stage 2: Laminar Downward Flow in Cleanroom (y: 110 -> 390)
        px = 540 + Math.abs(p.offset * 12) % 480;
        py = 110 + p.progress * 280;
        pColor = "#00ff88"; // Pure cleanroom air
      } else {
        // Stage 3: Return & Exhaust in Subfab
        px = 1000 - p.progress * 520;
        py = 410 + (p.offset > 0 ? 30 : -10);
        pColor = p.offset > 0 ? "#eab308" : "#94a3b8";
      }

      ctx.fillStyle = pColor;
      ctx.beginPath();
      ctx.arc(px, py, 1.8, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  drawCondensationDroplets() {
    const ctx = this.ctx;
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    this.droplets.forEach((d) => {
      d.y += d.speed;
      if (d.y > 255) {
        d.y = 180;
      }
      ctx.beginPath();
      ctx.moveTo(d.x, d.y);
      ctx.lineTo(d.x, d.y + d.len);
      ctx.stroke();
    });
  }

  drawHumidifierMist() {
    const ctx = this.ctx;
    this.mist.forEach((m) => {
      m.x += m.vx;
      m.y += m.vy;
      if (m.x > 290) {
        m.x = 265;
        m.y = 180 + Math.random() * 80;
      }
      ctx.fillStyle = `rgba(56, 189, 248, ${m.alpha})`;
      ctx.beginPath();
      ctx.arc(m.x, m.y, 2, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  drawComponentHighlights() {
    const ctx = this.ctx;

    // Highlight Hovered Component
    if (this.hoveredComponent && this.components[this.hoveredComponent]) {
      const box = this.components[this.hoveredComponent];
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(box.x - 3, box.y - 3, box.w + 6, box.h + 6);
      ctx.setLineDash([]);

      // Tooltip
      ctx.fillStyle = "rgba(11, 17, 32, 0.95)";
      ctx.strokeStyle = "#00e5ff";
      ctx.lineWidth = 1;
      const tx = Math.min(box.x, 880);
      const ty = Math.max(box.y - 35, 10);
      ctx.fillRect(tx, ty, 200, 26);
      ctx.strokeRect(tx, ty, 200, 26);

      ctx.fillStyle = "#fff";
      ctx.font = "bold 10px Inter, sans-serif";
      ctx.fillText(box.name, tx + 8, ty + 17);
    }

    // Highlight Selected Component
    if (this.selectedComponent && this.components[this.selectedComponent]) {
      const box = this.components[this.selectedComponent];
      ctx.strokeStyle = "#00ff88";
      ctx.lineWidth = 2;
      ctx.strokeRect(box.x - 2, box.y - 2, box.w + 4, box.h + 4);
    }
  }
}

window.BuronixAnimator = BuronixAnimator;
