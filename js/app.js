/**
 * BURONIX MASTER APPLICATION CONTROLLER
 * Coordinates UI events, simulation loop, SAC inference, telemetry HUD, and inspector modal
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
  const elEnergyKwh = document.getElementById('valEnergyKwh');
  const elSavingsPct = document.getElementById('valSavingsPct');
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
          <div class="inspect-param-row"><span>Điện năng tiết kiệm được:</span><strong>${(13.29 - 15.5 * Math.pow(t.u_mau, 3)).toFixed(2)} kW (-${((13.29 - 15.5 * Math.pow(t.u_mau, 3))/13.29 * 100).toFixed(1)}%)</strong></div>
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
          <div class="inspect-param-row"><span>Vận tốc gió mặt lọc:</span><strong>0.41 m/s (Chuẩn 0.32-0.52)</strong></div>
          <div class="inspect-param-row"><span>Công suất tiêu thụ / quạt:</span><strong>108.3 W / đơn vị</strong></div>
          <div class="inspect-param-row"><span>Tổng công suất 48 FFU:</span><strong>${((48 * 108.3)/1000).toFixed(2)} kW</strong></div>
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

  // Master Step Function
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
      // Run SAC AI Inference
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
        exhaust_m3_s: plant.BASE_EXHAUST * 0.59,
        door_fraction: plant.activeIncidents.doorOpen ? 0.45 : 0.0,
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
      // Baseline Mode: fixed commands
      u_mau_cmd = 0.95;
      u_ffu_cmd = 1.00;
    }

    // Advance Plant Dynamics
    const res = plant.step(u_mau_cmd, u_ffu_cmd, 60.0);
    const telem = res.telemetry;
    const sens = res.sensors;

    // Update Telemetry Charts
    charts.pushPoint(telem, sens, sacResult.uncertainty);

    // Update HUD Cards
    updateHud(telem, sens, sacResult);

    // Update Timeline Slider
    currentStep = (currentStep + 1) % totalSteps;
    if (elTimelineSlider) {
      elTimelineSlider.value = currentStep;
      const hours = Math.floor(currentStep / 60);
      const mins = currentStep % 60;
      elCurrentTimeLabel.textContent = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
    }
  }

  function updateHud(telem, sens, sacResult) {
    if (elPowerKw) elPowerKw.textContent = telem.current_power_kw.toFixed(2);
    if (elEnergyKwh) elEnergyKwh.textContent = telem.cumulative_kwh.toFixed(1);
    if (elSavingsPct) elSavingsPct.textContent = `${telem.cumulative_savings_pct.toFixed(1)}%`;
    if (elDp) elDp.textContent = sens.dp.toFixed(2);
    if (elTemp) elTemp.textContent = sens.temp.toFixed(2);
    if (elRh) elRh.textContent = sens.rh.toFixed(1);
    if (elParticles) elParticles.textContent = sens.particle_count.toFixed(1);
    if (elAmc) elAmc.textContent = sens.amc_nh3.toFixed(2);
    if (elMauHz) elMauHz.textContent = `${telem.mau_vfd_hz.toFixed(1)} Hz`;
    if (elFfuSpeed) elFfuSpeed.textContent = `${telem.ffu_speed_pct.toFixed(0)}%`;
    if (elAch) elAch.textContent = `${telem.ach.toFixed(1)}/h`;

    // SAC AI Brain telemetry
    if (elSacActionRaw) elSacActionRaw.textContent = `[${sacResult.a_raw[0].toFixed(2)}, ${sacResult.a_raw[1].toFixed(2)}]`;
    if (elSacUncertainty) elSacUncertainty.textContent = sacResult.uncertainty.toFixed(3);
    if (elUncertaintyBar) {
      const uPct = Math.min(100, (sacResult.uncertainty / 25.0) * 100);
      elUncertaintyBar.style.width = `${uPct}%`;
    }
    if (elMaskMauRange && elMaskMauPointer) {
      const loPct = ((sacResult.lo_mau - 0.70) / 0.30) * 100;
      const hiPct = ((sacResult.hi_mau - 0.70) / 0.30) * 100;
      const curPct = ((telem.u_mau - 0.70) / 0.30) * 100;
      elMaskMauRange.style.left = `${loPct}%`;
      elMaskMauRange.style.width = `${hiPct - loPct}%`;
      elMaskMauPointer.style.left = `${curPct}%`;
    }
    if (elTempVel) elTempVel.textContent = `${(plant.tempVelocity >= 0 ? '+' : '')}${plant.tempVelocity.toFixed(3)} °C/min`;
    if (elDpVel) elDpVel.textContent = `${(plant.dpVelocity >= 0 ? '+' : '')}${plant.dpVelocity.toFixed(3)} Pa/min`;
    if (elPlcStatus) elPlcStatus.textContent = sacResult.plc_status;
    if (elPlcReason) elPlcReason.textContent = sacResult.plc_reason;
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

  // Mode Selection Buttons
  const modeButtons = document.querySelectorAll('.mode-btn');
  modeButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      modeButtons.forEach((b) => {
        b.classList.remove('active-ai', 'active-baseline', 'active-split');
      });
      currentMode = btn.dataset.mode;
      if (currentMode === 'ai') btn.classList.add('active-ai');
      else if (currentMode === 'baseline') btn.classList.add('active-baseline');
      else btn.classList.add('active-split');
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
      console.log("Buronix Digital Twin reset to initial state.");
    });
  }

  console.log("Buronix Digital Twin ready.");
});
