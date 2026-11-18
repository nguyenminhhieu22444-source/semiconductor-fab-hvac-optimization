"""
Cleanroom Physics and Semiconductor Plant Dynamics Model
Based on SemiconFab Digital Twin Architecture (300mm Wafer Fab Bay 1 - Lithography & Track)
"""
import numpy as np

class CleanroomPlant:
    def __init__(self):
        # Physical Geometry (from SemiconFab TWIN-DATA-MAP)
        # Bay 1 (Lithography & Track): Length 30m, Width 18m, Height 5.22m (FFU plenum ceiling)
        self.length = 30.0  # m
        self.width = 18.0   # m
        self.height = 5.22  # m
        self.volume = self.length * self.width * self.height  # ~2818.8 m3
        self.floor_area = self.length * self.width            # 540 m2

        # Air properties (standard cleanroom condition: 22C, 101.3 kPa)
        self.rho_air = 1.204   # kg/m3
        self.cp_air = 1005.0   # J/(kg*K)
        self.mass_air = self.volume * self.rho_air # ~3394 kg

        # Cleanroom Equipment Specifications
        # FFU Grid: 48 units covering the ceiling (HEPA/ULPA filters)
        self.n_ffu = 48
        self.ffu_rated_airflow = 1800.0 / 3600.0  # m3/s per unit (~0.5 m3/s)
        self.ffu_rated_power = 220.0             # Watts per unit (0.22 kW)
        self.hepa_efficiency = 0.99999           # ULPA/HEPA 99.999% efficiency for 0.5um

        # MAU (Make-up Air Unit) for pressurization and fresh air conditioning
        self.mau_max_airflow = 10800.0 / 3600.0  # m3/s (3.0 m3/s max fresh air)
        self.mau_rated_power = 15000.0           # Watts (15 kW rated fan)

        # Baseline Exhaust: process tools pulling air to abatement
        self.base_exhaust_flow = 8500.0 / 3600.0 # m3/s

        # Environmental Targets / Limits (ISO 14644-1 Class 3)
        self.target_temp = 22.0                  # deg C
        self.temp_min = 21.5
        self.temp_max = 22.5
        self.target_rh = 42.5                    # % RH
        self.rh_min = 40.0
        self.rh_max = 45.0
        self.target_dp_min = 15.0                # Pa (Minimum positive pressure to prevent contamination)
        self.particle_class_limit = 1000.0       # particles/m3 (0.5 um, ISO Class 3 limit)

        # Thermal capacitance
        self.C_thermal = self.mass_air * self.cp_air # J/K (~3.41 MJ/K)

        self.reset()

    def reset(self):
        self.temp = 22.0            # deg C
        self.rh = 42.5              # %
        self.dp = 20.0              # Pa
        self.particle_count = 250.0 # particles/m3
        self.time_min = 0.0

    def compute_fan_powers(self, u_mau, u_ffu):
        """
        Fan Affinity Laws: Power is proportional to speed cubed (P ~ u^3)
        """
        p_mau = self.mau_rated_power * (u_mau ** 3)
        p_ffu = self.n_ffu * self.ffu_rated_power * (u_ffu ** 3)
        return p_mau, p_ffu  # in Watts

    def compute_pressure_steady(self, v_mau, v_exhaust):
        """
        Orifice flow relation for cleanroom envelope leakage:
        V_net = V_mau - V_exhaust = C_leak * sqrt(2 * dP / rho)
        """
        v_net = v_mau - v_exhaust
        if v_net <= 0:
            return max(0.0, 5.0 + v_net * 10.0) # Complete loss of positive pressure
        dp = 5.0 + 85.0 * (v_net ** 1.6)
        return np.clip(dp, 0.0, 50.0)

    def step(self, u_mau, u_ffu, q_mes_kw, particle_gen_rate, exhaust_override=None, dt_sec=60.0):
        """
        Simulate 1 time step (dt_sec) of cleanroom dynamics.
        """
        u_mau = float(np.clip(u_mau, 0.2, 1.0))
        u_ffu = float(np.clip(u_ffu, 0.2, 1.0))

        # 1. Airflows
        v_mau = u_mau * self.mau_max_airflow
        v_ffu = u_ffu * (self.n_ffu * self.ffu_rated_airflow)
        v_exhaust = exhaust_override if exhaust_override is not None else self.base_exhaust_flow

        # 2. Positive Differential Pressure (Delta P) Dynamics
        dp_steady = self.compute_pressure_steady(v_mau, v_exhaust)
        tau_p = 20.0 # seconds
        alpha_p = dt_sec / (tau_p + dt_sec)
        self.dp = float(self.dp + alpha_p * (dp_steady - self.dp))

        # 3. Particle Concentration Dynamics
        c_ambient = 500000.0 # Ambient outside corridor particle count
        leak_in = max(0.0, 15.0 - self.dp) * 0.02
        filter_rate = (v_ffu * self.hepa_efficiency + v_exhaust) / self.volume
        d_particles = (particle_gen_rate / self.volume) + (leak_in * c_ambient / self.volume) - (filter_rate * self.particle_count)
        self.particle_count = float(max(50.0, self.particle_count + d_particles * dt_sec))

        # 4. Thermal Dynamics with HVAC Chilled Water Coil Modulation
        p_mau, p_ffu = self.compute_fan_powers(u_mau, u_ffu)
        q_fan_kw = (p_mau + p_ffu) * 0.65 / 1000.0
        q_total_kw = q_mes_kw + q_fan_kw

        max_cooling_capacity = 30.0 + 130.0 * (0.35 * u_mau + 0.65 * u_ffu)
        cooling_demand = q_total_kw + 25.0 * (self.temp - self.target_temp)
        q_cooling_actual = np.clip(cooling_demand, 0.0, max_cooling_capacity)

        d_temp = ((q_total_kw - q_cooling_actual) * 1000.0) / self.C_thermal
        self.temp = float(self.temp + d_temp * dt_sec)

        # 5. Humidity Dynamics
        rh_target = 42.5
        d_rh = -0.02 * (self.temp - 22.0) - 0.005 * (self.rh - rh_target)
        self.rh = float(np.clip(self.rh + d_rh, 40.0, 45.0))

        self.time_min += dt_sec / 60.0
        return {
            "temp": self.temp,
            "rh": self.rh,
            "dp": self.dp,
            "particle_count": self.particle_count,
            "p_mau_kw": p_mau / 1000.0,
            "p_ffu_kw": p_ffu / 1000.0,
            "p_total_kw": (p_mau + p_ffu) / 1000.0
        }


def get_standard_mes_scenario(n_steps=1440, seed=42):
    """
    Standardized 24-hour MES production scenario for reproducible benchmark comparison.
    """
    np.random.seed(seed)
    times_hr = np.linspace(0, 24, n_steps, endpoint=False)
    q_mes = np.zeros(n_steps)
    particle_gen = np.zeros(n_steps)
    exhaust_override = [None] * n_steps
    sensor_glitch = [False] * n_steps
    ai_fault_injection = [False] * n_steps

    for i, t in enumerate(times_hr):
        if 0.0 <= t < 6.0:
            q_base = 25.0 + 4.0 * np.sin(t * np.pi / 3.0)
            p_gen = 120.0 + 20.0 * np.random.randn()
        elif 6.0 <= t < 8.0:
            ratio = (t - 6.0) / 2.0
            q_base = 25.0 + ratio * 65.0
            p_gen = 150.0 + ratio * 350.0 + 30.0 * np.random.randn()
        elif 8.0 <= t < 12.0:
            q_base = 90.0 + 8.0 * np.sin(t * 2.0)
            p_gen = 480.0 + 50.0 * np.random.randn()
        elif 12.0 <= t < 13.0:
            q_base = 60.0 + 5.0 * np.sin(t)
            p_gen = 280.0 + 30.0 * np.random.randn()
        elif 13.0 <= t < 18.0:
            q_base = 88.0 + 7.0 * np.cos(t * 1.5)
            p_gen = 470.0 + 40.0 * np.random.randn()
        elif 18.0 <= t < 22.0:
            q_base = 50.0 + 5.0 * np.sin(t)
            p_gen = 260.0 + 30.0 * np.random.randn()
        else:
            q_base = 28.0 + 4.0 * np.random.randn()
            p_gen = 130.0 + 20.0 * np.random.randn()

        # EVENT 1: AI fault test at 03:00 - 03:15
        if 3.0 <= t <= 3.25:
            ai_fault_injection[i] = True

        # EVENT 2: Physical door disturbance at 11:30 - 11:45
        if 11.5 <= t <= 11.75:
            exhaust_override[i] = 10200.0 / 3600.0
            p_gen += 400.0

        # EVENT 3: Sensor EMI noise at 16:30 - 16:45
        if 16.5 <= t <= 16.75:
            sensor_glitch[i] = True

        q_mes[i] = max(15.0, q_base + 1.5 * np.random.randn())
        particle_gen[i] = max(50.0, p_gen)

    return times_hr, q_mes, particle_gen, exhaust_override, sensor_glitch, ai_fault_injection
