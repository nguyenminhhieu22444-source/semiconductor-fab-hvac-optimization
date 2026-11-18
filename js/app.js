/**
 * BURONIX MASTER APPLICATION CONTROLLER
 * Coordinates UI events, instant mode transitions (Number Jumping), simulation loop,
 * SAC inference, telemetry HUD, and inspector modal.
 */

document.addEventListener('DOMContentLoaded', async () => {
  console.log("Buronix Digital Twin initializing...");

  // 1. Initialize System Components
  const plant = window.CLEANROOM_PLANT;
  const sac = window.SAC_RUNTIME;
  const animator = new BuronixAnimator('digitalTwinCanvas');
  const charts = new TelemetryCharts();

  // Load SAC weights
  await sac.loadWeights();

  // App State
  let currentMode = 'ai'; // 'baseline', 'ai', 'split'
  let isPlaying = true;
  let simSpeed = 1; // 1x, 5x, 20x
  let currentStep = 0;
  const totalSteps = 1440; // 24 hours * 60 min

  // DOM Elements
  const elPowerKw = document.getElementById('valPowerKw');
  const elPowerLabel = document.getElementById('valPowerLabel');
  const elEnergyKwh = document.getElementById('valEnergyKwh');
  const elSavingsLabel = document.getElementById('valSavingsLabel');
  const elEnergySub = document.getElementById('valEnergySub');
  const elDp = document.getElementById('valDp');
  const elTemp = document.getElementById('valTemp');
  const elRh = document.getElementById('valRh');
  const elParticles = document.getElementById('valParticles');
  const elAmc = document.getElementById('valAmc');
  const elMauHz = document.getElementById('valMauHz');
  const elFfuSpeed = document.getElementById('valFfuSpeed');
  const elAch = document.getElementById('valAch');

  // AI HUD Elements
  const elSacActionRaw = document.getElementById('valSacActionRaw');
  const elSacUncertainty = document.getElementById('valSacUncertainty');
  const elUncertaintyBar = document.getElementById('uncertaintyFillBar');
  const elMaskMauRange = document.getElementById('maskMauRange');
  const elMaskMauPointer = document.getElementById('maskMauPointer');
  const elMaskMauText = document.getElementById('maskMauText');
  const elTempVel = document.getElementById('valTempVel');
  const elDpVel = document.getElementById('valDpVel');
  const elPlcStatus = document.getElementById('valPlcStatus');
  const elPlcReason = document.getElementById('valPlcReason');

  // Timeline
  const elTimelineSlider = document.getElementById('timelineSlider');
  const elCurrentTimeLabel = document.getElementById('currentTimeLabel');

  // Inspector Elements
  const elInspector = document.getElementById('componentInspector');
  const elInspectorTitle = document.getElementById('inspectorTitle');
  const elInspectorBody = document.getElementById('inspectorBody');
  const elInspectorClose = document.getElementById('inspectorClose');

  if (elInspectorClose) {
    elInspectorClose.addEventListener('click', () => {
      elInspector.classList.remove('open');
    });
  }

  // Component Selection Callback from Animator
  window.onComponentSelect = (comp) => {
    openInspector(comp);
  };

  function openInspector(comp) {
    if (!elInspector) return;
    elInspector.classList.add('open');
    elInspectorTitle.textContent = comp.name;

    const t = plant;
    let html = `
      <div class="inspect-param-group">
        <div style="font-size:11px; font-weight:700; color:var(--cyan-glow); margin-bottom:6px;">THÔNG SỐ VẬN HÀNH THỜI GIAN THỰC</div>
        <div class="inspect-param-row"><span>Trạng thái module:</span><strong>HOẠT ĐỘNG (NOMINAL)</strong></div>
        <div class="inspect-param-row"><span>Chế độ kiểm soát:</span><strong style="color:${currentMode === 'ai' ? 'var(--cyan-glow)' : 'var(--red-alert)'};">${currentMode === 'ai' ? 'AI SAC TỐI ƯU' : 'BASELINE CỐ ĐỊNH'}</strong></div>
        <div class="inspect-param-row"><span>Lưu lượng gió qua:</span><strong>${(t.u_mau * 10800).toFixed(0)} m³/h</strong></div>
        <div class="inspect-param-row"><span>Tần số VFD:</span><strong>${(35.0 + (t.u_mau - 0.7) * 50).toFixed(1)} Hz</strong></div>
      </div>
    `;

    if (comp.type === 'MAU_FAN') {
      html += `
        <div class="inspect-param-group">
          <div style="font-size:11px; font-weight:700; color:var(--emerald-neon); margin-bottom:6px;">ĐẶC TÍNH CÔNG SUẤT ĐIỆN QUẠT</div>
          <div class="inspect-param-row"><span>Định mức động cơ:</span><strong>15.5 kW / 50 Hz</strong></div>
          <div class="inspect-param-row"><span>Công suất thực tế P_mau:</span><strong>${(15.5 * Math.pow(t.u_mau, 3)).toFixed(2)} kW</strong></div>
          <div class="inspect-param-row"><span>Công thức Affinity Law:</span><strong>P = P_rated × (f / 50)³</strong></div>
          <div class="inspect-param-row"><span>Điện năng tiết kiệm:</span><strong style="color:var(--emerald-neon);">${currentMode === 'ai' ? '-41.28% so với Baseline' : '0.0% (Chạy đầy tải)'}</strong></div>
        </div>
      `;
    } else if (comp.type === 'MAU_PRECOOL' || comp.type === 'MAU_RECOOL') {
      html += `
        <div class="inspect-param-group">
          <div style="font-size:11px; font-weight:700; color:var(--cyan-glow); margin-bottom:6px;">NHIỆT ĐỘNG HỌC DÀN LẠNH COIL (TSMC DATASET)</div>
          <div class="inspect-param-row"><span>Nguồn nước lạnh Chiller:</span><strong>6.0°C (Nước lạnh sâu)</strong></div>
          <div class="inspect-param-row"><span>Khí vào dàn sơ bộ:</span><strong>32.0°C</strong></div>
          <div class="inspect-param-row"><span>Khí ra dàn sơ bộ:</span><strong>17.7°C (Hạ nhiệt cảm)</strong></div>
          <div class="inspect-param-row"><span>Khí ra dàn lạnh sâu:</span><strong>11.06°C (Điểm sương tách ẩm)</strong></div>
          <div class="inspect-param-row"><span>Tách ẩm bão hòa:</span><strong>100% ngưng tụ rãnh thu nước</strong></div>
        </div>
      `;
    } else if (comp.type === 'MAU_REHEAT') {
      html += `
        <div class="inspect-param-group">
          <div style="font-size:11px; font-weight:700; color:var(--red-alert); margin-bottom:6px;">DÀN SẤY NÓNG TÁI NHIỆT (REHEAT)</div>
          <div class="inspect-param-row"><span>Nhiệt độ sau sấy:</span><strong>20.99°C (Chuẩn cấp phòng)</strong></div>
          <div class="inspect-param-row"><span>Công suất sấy bù:</span><strong>${(36.3 * (1.0 - (t.u_mau - 0.7)/0.3)).toFixed(1)} kW</strong></div>
          <div class="inspect-param-row"><span>Tối ưu chống Cold-Heat Offset:</span><strong>Tiết kiệm 18.39% nhiệt sấy</strong></div>
        </div>
      `;
    } else if (comp.type === 'FFU_GRID') {
      html += `
        <div class="inspect-param-group">
          <div style="font-size:11px; font-weight:700; color:var(--emerald-neon); margin-bottom:6px;">ĐẶC TÍNH 48 QUẠT TRẦN FFU (TABLE 3 DATASET)</div>
          <div class="inspect-param-row"><span>Số lượng module:</span><strong>48 quạt (Khung ma trận 12×4)</strong></div>
          <div class="inspect-param-row"><span>Vận tốc gió mặt lọc:</span><strong>${(0.32 + (t.u_ffu - 0.45) * 0.36).toFixed(2)} m/s</strong></div>
          <div class="inspect-param-row"><span>Công suất tiêu thụ:</span><strong>${(t.interpolateFfuPower(0.32 + (t.u_ffu - 0.45) * 0.36)).toFixed(1)} W / quạt</strong></div>
          <div class="inspect-param-row"><span>Tổng công suất 48 FFU:</span><strong>${((48 * t.interpolateFfuPower(0.32 + (t.u_ffu - 0.45) * 0.36))/1000).toFixed(2)} kW</strong></div>
          <div class="inspect-param-row"><span>Hiệu suất màng ULPA:</span><strong>99.999% (Hạt 0.1 µm)</strong></div>
        </div>
      `;
    } else if (comp.type === 'ASML_SCANNER') {
      html += `
        <div class="inspect-param-group">
          <div style="font-size:11px; font-weight:700; color:var(--cyan-glow); margin-bottom:6px;">MÁY QUANG KHẮC ASML TWINSCAN DUV (BAY 1)</div>
          <div class="inspect-param-row"><span>Tải nhiệt công nghệ (MES):</span><strong>90.0 kW (Định mức)</strong></div>
          <div class="inspect-param-row"><span>Tiêu chuẩn vi rung động:</span><strong>VC-D Curve (≤ 0.047 cm/s²)</strong></div>
          <div class="inspect-param-row"><span>Nhánh xả nhiệt trực tiếp:</span><strong>2,000 m³/h</strong></div>
          <div class="inspect-param-row"><span>Độ nhạy nhiệt độ:</span><strong>±0.1°C bảo vệ thấu kính</strong></div>
        </div>
      `;
    }

    elInspectorBody.innerHTML = html;
  }

  // Animation trigger for Number Popping
  function triggerNumberPop() {
    const nums = document.querySelectorAll('.kpi-num');
    nums.forEach((el) => {
      el.classList.remove('number-pop');
      void el.offsetWidth; // trigger reflow
      el.classList.add('number-pop');
      setTimeout(() => el.classList.remove('number-pop'), 300);
    });
  }

  // Instant Mode Switching (Number Jumping)
  function setMode(mode) {
    currentMode = mode;

    if (mode === 'baseline') {
      // 1. Instantly snap plant to Baseline parameters
      plant.u_mau = 0.95;
      plant.u_ffu = 1.00;
      plant.currentPowerKw = 19.72;
      plant.cumulativeEnergyKwh = 1028.66;
      plant.dp = 21.45;
      plant.temp = 22.00;
      plant.rh = 42.3;
      plant.particleCount = 38.2;
      plant.amcNh3 = 0.24;

      // 2. Instantly update all HUD Cards
      elPowerKw.textContent = "19.72";
      elPowerLabel.textContent = "Tiết kiệm tức thời: 0.0% (Gốc)";

      elEnergyKwh.textContent = "1028.7";
      elSavingsLabel.textContent = "Tiết kiệm 24h: 0.0% (Gốc)";
      elEnergySub.textContent = "Cắt giảm 0.0 kWh";

      elDp.textContent = "21.45";
      elTemp.textContent = "22.00";
      elRh.textContent = "42.3";
      elParticles.textContent = "38.2";
      elAmc.textContent = "0.24";
      elMauHz.textContent = "47.5 Hz";
      elFfuSpeed.textContent = "48 FFU: 100% Tốc độ";
      elAch.textContent = "26.7 ACH";

      // AI HUD
      elSacActionRaw.textContent = "[0.00, 0.00]";
      elSacUncertainty.textContent = "0.000";
      elUncertaintyBar.style.width = "0%";
      elMaskMauText.textContent = "0.95 — 1.00 (Khóa cố định)";
      elMaskMauRange.style.left = "83%";
      elMaskMauRange.style.width = "17%";
      elMaskMauPointer.style.left = "83%";
      elPlcStatus.textContent = "BASELINE_OVERRIDE";
      elPlcReason.textContent = "Fixed ASHRAE G36 rules without AI optimization";

      charts.pushPoint(
        { current_power_kw: 19.72, baseline_power_kw: 19.72 },
        { dp: 21.45, temp: 22.00, rh: 42.3, particle_count: 38.2 },
        0.0
      );

    } else if (mode === 'ai') {
      // 1. Instantly snap plant to AI Optimized parameters (Nhánh Phuoc)
      plant.u_mau = 0.79;
      plant.u_ffu = 0.79;
      plant.currentPowerKw = 11.58;
      plant.cumulativeEnergyKwh = 568.70;
      plant.dp = 16.28;
      plant.temp = 22.01;
      plant.rh = 41.4;
      plant.particleCount = 64.8;
      plant.amcNh3 = 0.28;

      // 2. Instantly update all HUD Cards
      elPowerKw.textContent = "11.58";
      elPowerLabel.textContent = "Tiết kiệm tức thời: -41.3%";

      elEnergyKwh.textContent = "568.7";
      elSavingsLabel.textContent = "Tiết kiệm 24h: +44.71%";
      elEnergySub.textContent = "Cắt giảm 459.9 kWh";

      elDp.textContent = "16.28";
      elTemp.textContent = "22.01";
      elRh.textContent = "41.4";
      elParticles.textContent = "64.8";
      elAmc.textContent = "0.28";
      elMauHz.textContent = "39.5 Hz";
      elFfuSpeed.textContent = "48 FFU: 79% Tốc độ";
      elAch.textContent = "18.4 ACH";

      // AI HUD
      elSacActionRaw.textContent = "[-0.15, 0.35]";
      elSacUncertainty.textContent = "0.123";
      elUncertaintyBar.style.width = "12%";
      elMaskMauText.textContent = "0.70 — 1.00 (Tự do tối ưu)";
      elMaskMauRange.style.left = "0%";
      elMaskMauRange.style.width = "100%";
      elMaskMauPointer.style.left = "30%";
      elPlcStatus.textContent = "SAFE_ACCEPTED";
      elPlcReason.textContent = "Nominal SAC control within limits";

      charts.pushPoint(
        { current_power_kw: 11.58, baseline_power_kw: 19.72 },
        { dp: 16.28, temp: 22.01, rh: 41.4, particle_count: 64.8 },
        0.123
      );

    } else {
      // Split mode
      elPowerLabel.textContent = "Đối chuẩn kép: 11.58 kW vs 19.72 kW";
      elSavingsLabel.textContent = "Chênh lệch tiết kiệm: +44.71%";
    }

    // Trigger snappy visual popping effect
    triggerNumberPop();

    // Re-render currently inspected component if drawer is open
    if (elInspector && elInspector.classList.contains('open') && animator.selectedComponent) {
      openInspector(animator.components[animator.selectedComponent]);
    }
  }

  // Master Step Function (Continuous Animation Loop)
  function executeSimulationStep() {
    let u_mau_cmd = 0.95;
    let u_ffu_cmd = 1.00;
    let sacResult = {
      a_raw: [-0.15, 0.35],
      uncertainty: 0.12,
      lo_mau: 0.70,
      hi_mau: 1.00,
      plc_status: "SAFE_ACCEPTED",
      plc_reason: "Nominal SAC control"
    };

    if (currentMode === 'ai' || currentMode === 'split') {
      const currentSensors = {
        dp: plant.dp,
        particle_count: plant.particleCount,
        particles_05: plant.particles05,
        temp: plant.temp,
        rh: plant.rh,
        amc_nh3: plant.amcNh3,
        mau_filter_dp: plant.mauFilterDp
      };
      const currentDisturbance = {
        equipment_kw: 25.0,
        particles_per_min: 110.0,
        exhaust_m3_s: 1.39,
        door_fraction: plant.activeIncidents.doorOpen ? 0.40 : 0.0,
        outdoor_temp_c: 30.0,
        outdoor_rh_pct: 65.0,
        amc_multiplier: 1.0
      };

      sacResult = sac.predict(
        currentSensors,
        currentDisturbance,
        null,
        plant.u_mau,
        plant.u_ffu,
        plant.tempVelocity,
        plant.dpVelocity
      );

      u_mau_cmd = sacResult.u_mau;
      u_ffu_cmd = sacResult.u_ffu;
    } else {
      u_mau_cmd = 0.95;
      u_ffu_cmd = 1.00;
    }

    // Advance Plant Dynamics
    const res = plant.step(u_mau_cmd, u_ffu_cmd, 60.0);
    const telem = res.telemetry;
    const sens = res.sensors;

    // Update Telemetry Charts
    charts.pushPoint(telem, sens, sacResult.uncertainty);

    // Update HUD Cards dynamically if not in fixed baseline view
    if (currentMode === 'ai') {
      elPowerKw.textContent = telem.current_power_kw.toFixed(2);
      elEnergyKwh.textContent = telem.cumulative_kwh.toFixed(1);
      elSavingsLabel.textContent = `Tiết kiệm 24h: +${telem.cumulative_savings_pct.toFixed(1)}%`;
      elDp.textContent = sens.dp.toFixed(2);
      elTemp.textContent = sens.temp.toFixed(2);
      elRh.textContent = sens.rh.toFixed(1);
      elParticles.textContent = sens.particle_count.toFixed(1);
      elAmc.textContent = sens.amc_nh3.toFixed(2);
      elMauHz.textContent = `${telem.mau_vfd_hz.toFixed(1)} Hz`;
      elFfuSpeed.textContent = `48 FFU: ${telem.ffu_speed_pct.toFixed(0)}% Tốc độ`;
      elAch.textContent = `${telem.ach.toFixed(1)} ACH`;

      elSacActionRaw.textContent = `[${sacResult.a_raw[0].toFixed(2)}, ${sacResult.a_raw[1].toFixed(2)}]`;
      elSacUncertainty.textContent = sacResult.uncertainty.toFixed(3);
      const uPct = Math.min(100, (sacResult.uncertainty / 25.0) * 100);
      elUncertaintyBar.style.width = `${uPct}%`;
      const curPct = ((telem.u_mau - 0.70) / 0.30) * 100;
      elMaskMauPointer.style.left = `${curPct}%`;
      elTempVel.textContent = `${(plant.tempVelocity >= 0 ? '+' : '')}${plant.tempVelocity.toFixed(3)} °C/min`;
      elDpVel.textContent = `${(plant.dpVelocity >= 0 ? '+' : '')}${plant.dpVelocity.toFixed(3)} Pa/min`;
      elPlcStatus.textContent = sacResult.plc_status;
      elPlcReason.textContent = sacResult.plc_reason;
    }

    // Update Timeline Slider
    currentStep = (currentStep + 1) % totalSteps;
    if (elTimelineSlider) {
      elTimelineSlider.value = currentStep;
      const hours = Math.floor(currentStep / 60);
      const mins = currentStep % 60;
      elCurrentTimeLabel.textContent = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
    }
  }

  // Simulation Loop Timer
  let intervalId = setInterval(() => {
    if (isPlaying) {
      executeSimulationStep();
    }
  }, 1000 / simSpeed);

  function resetSimSpeed(newSpeed) {
    simSpeed = newSpeed;
    clearInterval(intervalId);
    intervalId = setInterval(() => {
      if (isPlaying) {
        executeSimulationStep();
      }
    }, 1000 / simSpeed);
  }

  // Playback Event Listeners
  const btnPlayPause = document.getElementById('btnPlayPause');
  if (btnPlayPause) {
    btnPlayPause.addEventListener('click', () => {
      isPlaying = !isPlaying;
      btnPlayPause.textContent = isPlaying ? '⏸️ Tạm Dừng' : '▶️ Tiếp Tục';
    });
  }

  const speedButtons = document.querySelectorAll('.btn-speed');
  speedButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      speedButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const speed = parseInt(btn.dataset.speed, 10);
      resetSimSpeed(speed);
    });
  });

  if (elTimelineSlider) {
    elTimelineSlider.addEventListener('input', (e) => {
      currentStep = parseInt(e.target.value, 10);
      const hours = Math.floor(currentStep / 60);
      const mins = currentStep % 60;
      elCurrentTimeLabel.textContent = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
    });
  }

  // Mode Selection Buttons (Instant Number Jumping)
  const modeButtons = document.querySelectorAll('.mode-btn');
  modeButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      modeButtons.forEach((b) => {
        b.classList.remove('active-ai', 'active-baseline', 'active-split');
      });
      const mode = btn.dataset.mode;
      if (mode === 'ai') btn.classList.add('active-ai');
      else if (mode === 'baseline') btn.classList.add('active-baseline');
      else btn.classList.add('active-split');

      // Execute instant jump!
      setMode(mode);
    });
  });

  // Incident Trigger Buttons
  const incidentBtns = document.querySelectorAll('.incident-btn');
  incidentBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const inc = btn.dataset.incident;
      plant.activeIncidents[inc] = !plant.activeIncidents[inc];
      if (plant.activeIncidents[inc]) {
        btn.classList.add('active-incident');
      } else {
        btn.classList.remove('active-incident');
      }
    });
  });

  // Reset button
  const btnReset = document.getElementById('btnReset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      plant.reset();
      currentStep = 0;
      incidentBtns.forEach((b) => {
        b.classList.remove('active-incident');
        const inc = b.dataset.incident;
        plant.activeIncidents[inc] = false;
      });
      setMode(currentMode);
    });
  }

  // Initial trigger for AI mode
  setMode('ai');
  console.log("Buronix Digital Twin ready.");
});
