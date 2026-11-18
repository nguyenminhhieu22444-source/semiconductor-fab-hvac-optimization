/**
 * BURONIX TELEMETRY CHARTS DASHBOARD (PURE CANVAS 2D)
 * Real-time High-frequency Waveforms: Power, Pressure, Thermal & SAC Uncertainty
 * Zero external dependencies, ultra-fast 60 FPS rendering
 */

class TelemetryCharts {
  constructor() {
    this.historyLen = 80;
    this.data = {
      time: [],
      powerAi: [],
      powerBaseline: [],
      dp: [],
      temp: [],
      rh: [],
      particles: [],
      uncertainty: []
    };

    this.chartPower = document.getElementById('chartPowerCanvas');
    this.chartDp = document.getElementById('chartDpCanvas');
    this.chartEnv = document.getElementById('chartEnvCanvas');

    // Handle canvas sizing
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const containers = [this.chartPower, this.chartDp, this.chartEnv];
    containers.forEach((c) => {
      if (c && c.parentElement) {
        c.width = c.parentElement.clientWidth - 20;
        c.height = c.parentElement.clientHeight - 35;
      }
    });
  }

  pushPoint(telemetry, sensors, uncertainty) {
    this.data.powerAi.push(telemetry.current_power_kw || 11.5);
    this.data.powerBaseline.push(telemetry.baseline_power_kw || 19.72);
    this.data.dp.push(sensors.dp || 18.0);
    this.data.temp.push(sensors.temp || 22.0);
    this.data.rh.push(sensors.rh || 41.5);
    this.data.particles.push(sensors.particle_count || 60.0);
    this.data.uncertainty.push(uncertainty || 0.12);

    if (this.data.powerAi.length > this.historyLen) {
      this.data.powerAi.shift();
      this.data.powerBaseline.shift();
      this.data.dp.shift();
      this.data.temp.shift();
      this.data.rh.shift();
      this.data.particles.shift();
      this.data.uncertainty.shift();
    }

    this.render();
  }

  render() {
    this.renderPowerChart();
    this.renderDpChart();
    this.renderEnvChart();
  }

  drawGrid(ctx, w, h, yMin, yMax, unit, yTicks = 4) {
    ctx.strokeStyle = "rgba(51, 65, 85, 0.35)";
    ctx.lineWidth = 1;
    ctx.font = "9px JetBrains Mono, monospace";
    ctx.fillStyle = "#64748b";

    for (let i = 0; i <= yTicks; i++) {
      const y = h - (i / yTicks) * (h - 15) - 5;
      ctx.beginPath();
      ctx.moveTo(35, y);
      ctx.lineTo(w, y);
      ctx.stroke();

      const val = yMin + (i / yTicks) * (yMax - yMin);
      ctx.fillText(`${val.toFixed(1)}${unit}`, 2, y + 3);
    }
  }

  renderPowerChart() {
    if (!this.chartPower) return;
    const ctx = this.chartPower.getContext('2d');
    const w = this.chartPower.width;
    const h = this.chartPower.height;
    ctx.clearRect(0, 0, w, h);

    const yMin = 5.0, yMax = 25.0;
    this.drawGrid(ctx, w, h, yMin, yMax, "kW");

    const n = this.data.powerAi.length;
    if (n < 2) return;

    const xStep = (w - 40) / (this.historyLen - 1);

    // 1. Fill Savings Area between Baseline and AI
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = 38 + i * xStep;
      const yBase = h - ((this.data.powerBaseline[i] - yMin) / (yMax - yMin)) * (h - 15) - 5;
      if (i === 0) ctx.moveTo(x, yBase);
      else ctx.lineTo(x, yBase);
    }
    for (let i = n - 1; i >= 0; i--) {
      const x = 38 + i * xStep;
      const yAi = h - ((this.data.powerAi[i] - yMin) / (yMax - yMin)) * (h - 15) - 5;
      ctx.lineTo(x, yAi);
    }
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 255, 136, 0.15)";
    ctx.fill();

    // 2. Draw Baseline Curve (Red/Muted)
    ctx.strokeStyle = "rgba(239, 68, 68, 0.85)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = 38 + i * xStep;
      const y = h - ((this.data.powerBaseline[i] - yMin) / (yMax - yMin)) * (h - 15) - 5;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // 3. Draw AI SAC Curve (Cyan Glow)
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 2.2;
    ctx.shadowColor = "#00e5ff";
    ctx.shadowBlur = 6;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = 38 + i * xStep;
      const y = h - ((this.data.powerAi[i] - yMin) / (yMax - yMin)) * (h - 15) - 5;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  renderDpChart() {
    if (!this.chartDp) return;
    const ctx = this.chartDp.getContext('2d');
    const w = this.chartDp.width;
    const h = this.chartDp.height;
    ctx.clearRect(0, 0, w, h);

    const yMin = 10.0, yMax = 25.0;
    this.drawGrid(ctx, w, h, yMin, yMax, "Pa");

    // Safety Red Barrier Line at 15.0 Pa
    const yLimit = h - ((15.0 - yMin) / (yMax - yMin)) * (h - 15) - 5;
    ctx.strokeStyle = "rgba(239, 68, 68, 0.7)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(35, yLimit);
    ctx.lineTo(w, yLimit);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ef4444";
    ctx.font = "8px JetBrains Mono, monospace";
    ctx.fillText("GIỚI HẠN AN TOÀN 15.0 Pa", w - 120, yLimit - 4);

    const n = this.data.dp.length;
    if (n < 2) return;

    const xStep = (w - 40) / (this.historyLen - 1);

    // Draw DP Curve (Emerald Neon)
    ctx.strokeStyle = "#00ff88";
    ctx.lineWidth = 2.0;
    ctx.shadowColor = "#00ff88";
    ctx.shadowBlur = 6;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = 38 + i * xStep;
      const y = h - ((this.data.dp[i] - yMin) / (yMax - yMin)) * (h - 15) - 5;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  renderEnvChart() {
    if (!this.chartEnv) return;
    const ctx = this.chartEnv.getContext('2d');
    const w = this.chartEnv.width;
    const h = this.chartEnv.height;
    ctx.clearRect(0, 0, w, h);

    const yMin = 20.0, yMax = 24.0;
    this.drawGrid(ctx, w, h, yMin, yMax, "°C");

    const n = this.data.temp.length;
    if (n < 2) return;

    const xStep = (w - 40) / (this.historyLen - 1);

    // Target corridor: 21.7 - 22.3
    const yTop = h - ((22.3 - yMin) / (yMax - yMin)) * (h - 15) - 5;
    const yBot = h - ((21.7 - yMin) / (yMax - yMin)) * (h - 15) - 5;
    ctx.fillStyle = "rgba(56, 189, 248, 0.1)";
    ctx.fillRect(38, yTop, w - 38, yBot - yTop);

    // Temp Curve (Amber Warm)
    ctx.strokeStyle = "#ffb800";
    ctx.lineWidth = 2.0;
    ctx.shadowColor = "#ffb800";
    ctx.shadowBlur = 5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = 38 + i * xStep;
      const y = h - ((this.data.temp[i] - yMin) / (yMax - yMin)) * (h - 15) - 5;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }
}

window.TelemetryCharts = TelemetryCharts;
