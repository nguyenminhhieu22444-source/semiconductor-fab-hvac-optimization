"""Shared, reduced-order Bay 1 model with explicit engineering units."""

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CONFIG = json.loads(Path(__file__).with_name("bay1_config.json").read_text(encoding="utf-8"))
AIR = CONFIG["air"]
MAU = CONFIG["mau"]
FFU = CONFIG["ffu"]
PRESSURE = CONFIG["pressure"]
COOLING = CONFIG["cooling"]
CONTAMINANTS = CONFIG["contaminants"]
LIMITS = CONFIG["limits"]
CONTROL = CONFIG["control"]


@dataclass(frozen=True)
class Disturbance:
    exhaust_m3_s: float
    equipment_kw: float
    particles_per_min: float
    outdoor_temp_c: float = 29.93
    outdoor_rh_pct: float = 60.0
    door_fraction: float = 0.0
    amc_multiplier: float = 1.0


@dataclass(frozen=True)
class ThermalForcing:
    heat_source_kw: float
    conductance_kw_k: float
    coil_capacity_kw: float

    @property
    def load_at_setpoint_kw(self):
        return self.heat_source_kw - self.conductance_kw_k * CONTROL["target_temp_c"]


def thermal_step(temp, coil, forcing, dt_sec):
    """Physical reference with the feedback target held over one time step."""
    demand = forcing.load_at_setpoint_kw + COOLING["room_coil_feedback_kw_k"] * (temp - CONTROL["target_temp_c"])
    target = max(0.0, min(forcing.coil_capacity_kw, demand))
    tau = COOLING["room_coil_time_constant_s"]
    next_coil = approach(coil, target, tau, dt_sec)
    average_coil = target + (coil - next_coil) * tau / dt_sec
    next_temp = approach(
        temp, (forcing.heat_source_kw - average_coil) / forcing.conductance_kw_k,
        AIR["effective_thermal_mass_kj_k"] / forcing.conductance_kw_k, dt_sec,
    )
    return next_temp, next_coil, average_coil


def saturation_pressure(temp_c):
    return 0.61094 * math.exp(17.625 * temp_c / (temp_c + 243.04))


def humidity_ratio(temp_c, rh_pct):
    vapor = saturation_pressure(temp_c) * rh_pct / 100.0
    return 0.62198 * vapor / (AIR["pressure_kpa"] - vapor)


def relative_humidity(temp_c, water_ratio):
    vapor = AIR["pressure_kpa"] * water_ratio / (0.62198 + water_ratio)
    return 100.0 * vapor / saturation_pressure(temp_c)


def dewpoint(water_ratio):
    if water_ratio <= 0.0:
        return -100.0
    vapor = AIR["pressure_kpa"] * water_ratio / (0.62198 + water_ratio)
    log_ratio = math.log(vapor / 0.61094)
    return 243.04 * log_ratio / (17.625 - log_ratio)


def enthalpy(temp_c, water_ratio):
    return AIR["specific_heat_kj_kg_k"] * temp_c + water_ratio * (2501.0 + 1.86 * temp_c)


def approach(initial, target, tau_s, dt_s):
    return initial + (target - initial) * -math.expm1(-dt_s / tau_s)


def well_mixed(initial, source, removal, volume, dt_s):
    if removal == 0.0:
        return initial + source * dt_s / volume
    return approach(initial, source / removal, volume / removal, dt_s)


def environment_violations(state):
    limits = (
        ("temp", LIMITS["temp_min"], LIMITS["temp_max"]),
        ("rh", LIMITS["rh_min"], LIMITS["rh_max"]),
        ("dp", LIMITS["dp_min"], LIMITS["dp_max"]),
        ("particle_count", 0.0, LIMITS["particles_01_max"]),
        ("particles_05", 0.0, LIMITS["particles_05_max"]),
        ("amc_nh3", 0.0, LIMITS["nh3_max"]),
    )
    return [name for name, low, high in limits if not low <= state[name] <= high]


def leakage_flow(dp_pa, door_fraction):
    crack = PRESSURE["crack_flow_m3_s_at_18_pa"] * (abs(dp_pa) / 18.0) ** PRESSURE["crack_flow_exponent"]
    door = door_fraction * PRESSURE["door_flow_m3_s_pa_sqrt"] * math.sqrt(abs(dp_pa))
    relief = PRESSURE["relief_flow_m3_s_pa"] * max(0.0, dp_pa - PRESSURE["relief_opening_pa"])
    return math.copysign(crack + door, dp_pa) + relief


@lru_cache(maxsize=4096)
def supply_conditions(u_mau, outdoor_temp_c, outdoor_rh_pct):
    """Two wet-coil stages and reheat with separate thermal capacity limits."""
    flow_m3_s = MAU["max_airflow_m3h"] * u_mau / 3600.0
    mass_flow = flow_m3_s * AIR["dry_density_kg_m3"]
    outdoor_water = humidity_ratio(outdoor_temp_c, outdoor_rh_pct)
    if mass_flow == 0.0:
        return outdoor_temp_c, outdoor_water, 0.0, 0.0, 0.0

    def cooled(inlet_temp, inlet_water, target_temp, capacity):
        inlet_h = enthalpy(inlet_temp, inlet_water)
        target_temp = min(inlet_temp, target_temp)
        target_water = min(inlet_water, humidity_ratio(target_temp, 100.0))
        if inlet_h - enthalpy(target_temp, target_water) <= capacity / mass_flow:
            return target_temp, target_water, mass_flow * (inlet_h - enthalpy(target_temp, target_water))
        target_h = inlet_h - capacity / mass_flow
        lo, hi = target_temp, inlet_temp
        for _ in range(18):
            mid = (lo + hi) / 2.0
            if enthalpy(mid, min(inlet_water, humidity_ratio(mid, 100.0))) < target_h:
                lo = mid
            else:
                hi = mid
        return hi, min(inlet_water, humidity_ratio(hi, 100.0)), capacity

    t1, w1, precool_kw = cooled(outdoor_temp_c, outdoor_water, MAU["precool_target_c"], MAU["precool_capacity_kw"])
    t2, w2, recool_kw = cooled(t1, w1, MAU["supply_dewpoint_target_c"], MAU["recool_capacity_kw"])
    moist_cp = AIR["specific_heat_kj_kg_k"] + 1.86 * w2
    reheat_kw = min(MAU["reheat_capacity_kw"], mass_flow * moist_cp * max(0.0, MAU["supply_temp_target_c"] - t2))
    return t2 + reheat_kw / (mass_flow * moist_cp), w2, precool_kw, recool_kw, reheat_kw


class CleanroomPlant:
    def __init__(self):
        geometry = CONFIG["geometry"]
        self.length = geometry["length_m"]
        self.width = geometry["width_m"]
        self.height = geometry["clear_height_m"]
        self.volume = self.length * self.width * self.height
        self.mau_max_airflow = MAU["max_airflow_m3h"] / 3600.0
        self.n_ffu = FFU["count"]
        self.ffu_rated_airflow = FFU["rated_face_velocity_m_s"] * FFU["face_area_m2"]
        self.base_exhaust_flow = sum(CONFIG["exhaust_m3h"].values()) / 3600.0
        self.reset()

    def reset(self):
        self.outdoor_temp = 29.93
        self.outdoor_rh = 60.0
        self.time_min = 0.0
        self.state = {
            "temp": CONTROL["target_temp_c"],
            "rh": CONTROL["target_rh_pct"],
            "dp": CONTROL["pressure_target_pa"],
            "particle_count": 100.0,
            "particles_05": 12.0,
            "amc_nh3": 0.10,
            "room_coil_kw": 30.0,
        }

    def compute_fan_powers(self, u_mau, u_ffu):
        """Return electrical watts. FFU points are from a published estimate table."""
        velocity = FFU["rated_face_velocity_m_s"] * u_ffu
        speeds = FFU["power_curve_velocity_m_s"]
        watts = FFU["power_curve_w"]
        for index, upper in enumerate(speeds[1:], 1):
            if velocity <= upper:
                fraction = (velocity - speeds[index - 1]) / (upper - speeds[index - 1])
                ffu_w = watts[index - 1] + fraction * (watts[index] - watts[index - 1])
                break
        else:
            ffu_w = watts[-1]
        return 1000.0 * MAU["rated_fan_kw"] * u_mau**3, self.n_ffu * ffu_w

    def compute_pressure_steady(self, v_mau, v_exhaust, door_fraction=0.0):
        net = v_mau - v_exhaust
        simple_dp = math.copysign(
            18.0 * (abs(net) / PRESSURE["crack_flow_m3_s_at_18_pa"]) ** (1.0 / PRESSURE["crack_flow_exponent"]),
            net,
        )
        if door_fraction == 0.0 and simple_dp <= PRESSURE["relief_opening_pa"]:
            return simple_dp
        lo, hi = (simple_dp, 0.0) if net < 0.0 else (0.0, simple_dp)
        if net > 0.0:
            hi = min(hi, PRESSURE["relief_opening_pa"] + net / PRESSURE["relief_flow_m3_s_pa"])
        for _ in range(16):
            mid = (lo + hi) / 2.0
            if leakage_flow(mid, door_fraction) < net:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    def sensor_data(self, disturbance):
        return {
            **self.state,
            "exhaust_flow": disturbance.exhaust_m3_s,
            "door_fraction": disturbance.door_fraction,
            "outdoor_temp": disturbance.outdoor_temp_c,
            "outdoor_rh": disturbance.outdoor_rh_pct,
            "amc_multiplier": disturbance.amc_multiplier,
            "mau_filter_dp": MAU["filter_dp_rated_pa"],
            "age_s": 0.0,
        }

    def predict(self, u_mau, u_ffu, state, disturbance, dt_sec=60.0, *, thermal_transition=thermal_step):
        """A pure transition used for simulation and prediction."""
        if not math.isfinite(dt_sec) or dt_sec <= 0.0:
            raise ValueError("dt_sec must be finite and positive")
        q_mau = u_mau * self.mau_max_airflow
        q_ffu = u_ffu * self.n_ffu * self.ffu_rated_airflow
        q_exhaust = disturbance.exhaust_m3_s
        dp_steady = self.compute_pressure_steady(q_mau, q_exhaust, disturbance.door_fraction)
        dp = approach(state["dp"], dp_steady, PRESSURE["time_constant_s"], dt_sec)
        # Quasi-steady net flow closes the volume balance. Door mixing adds equal counterflows.
        q_mix = disturbance.door_fraction * PRESSURE["door_mixing_m3_s"]
        q_in = max(0.0, q_exhaust - q_mau) + q_mix
        q_out = q_exhaust + max(0.0, q_mau - q_exhaust) + q_mix

        particle_source = disturbance.particles_per_min / 60.0
        particle_removal = q_out + FFU["particle_efficiency"] * q_ffu
        particles = well_mixed(
            state["particle_count"],
            particle_source + q_mau * CONTAMINANTS["supply_particles_01_m3"] + q_in * CONTAMINANTS["corridor_particles_01_m3"],
            particle_removal, self.volume, dt_sec,
        )
        particles_05 = well_mixed(
            state["particles_05"],
            particle_source * CONTAMINANTS["generation_fraction_05"] + q_mau * CONTAMINANTS["supply_particles_05_m3"] + q_in * CONTAMINANTS["corridor_particles_05_m3"],
            particle_removal, self.volume, dt_sec,
        )
        nh3_source = CONTAMINANTS["nh3_generation_ppb_m3_s_at_150_particles_min"] * disturbance.particles_per_min / 150.0
        nh3 = well_mixed(
            state["amc_nh3"],
            nh3_source * disturbance.amc_multiplier + q_mau * CONTAMINANTS["supply_nh3_ppb"] + q_in * CONTAMINANTS["corridor_nh3_ppb"],
            q_out + FFU["recirculation_nh3_efficiency"] * q_ffu, self.volume, dt_sec,
        )

        supply_temp, supply_water, precool_kw, recool_kw, reheat_kw = supply_conditions(
            u_mau, disturbance.outdoor_temp_c, disturbance.outdoor_rh_pct
        )
        outdoor_water = humidity_ratio(disturbance.outdoor_temp_c, disturbance.outdoor_rh_pct)
        water = well_mixed(
            humidity_ratio(state["temp"], state["rh"]),
            q_mau * supply_water + q_in * outdoor_water + AIR["room_moisture_kg_h"] / (3600.0 * AIR["dry_density_kg_m3"]),
            q_out, self.volume, dt_sec,
        )

        p_mau_w, p_ffu_w = self.compute_fan_powers(u_mau, u_ffu)
        air_capacity = AIR["dry_density_kg_m3"] * AIR["specific_heat_kj_kg_k"]
        conductance = AIR["envelope_kw_k"] + air_capacity * (q_mau + q_in)
        heat_source = (
            disturbance.equipment_kw + (MAU["fan_heat_fraction_to_room"] * p_mau_w + p_ffu_w) / 1000.0
            + (AIR["envelope_kw_k"] + air_capacity * q_in) * disturbance.outdoor_temp_c
            + air_capacity * q_mau * supply_temp
        )
        forcing = ThermalForcing(heat_source, conductance, COOLING["room_coil_capacity_kw"] * math.sqrt(u_ffu))
        temp, coil_kw, average_coil_kw = thermal_transition(
            state["temp"], state["room_coil_kw"], forcing, dt_sec,
        )
        # At saturation the excess water is condensate, rather than a room RH above 100%.
        rh = min(100.0, relative_humidity(temp, water))
        fan_kw = (p_mau_w + p_ffu_w) / 1000.0
        return {
            "temp": temp, "rh": rh, "dp": dp, "dp_steady": dp_steady,
            "particle_count": particles, "particles_05": particles_05, "amc_nh3": nh3,
            "room_coil_kw": coil_kw,
            "p_mau_kw": p_mau_w / 1000.0, "p_ffu_kw": p_ffu_w / 1000.0, "p_total_kw": fan_kw,
            "estimated_hvac_electric_kw": fan_kw + (precool_kw + recool_kw + average_coil_kw) / COOLING["assumed_cooling_cop"] + reheat_kw,
            "mau_vfd_hz": MAU["rated_hz"] * u_mau,
            "mau_filter_dp": MAU["filter_dp_rated_pa"],
            "mau_supply_temp": supply_temp, "mau_supply_dewpoint": dewpoint(supply_water),
            "mau_precool_kw": precool_kw, "mau_recool_kw": recool_kw, "mau_reheat_kw": reheat_kw,
            "mau_cw_valve_pct": 100.0 * (precool_kw + recool_kw) / (MAU["precool_capacity_kw"] + MAU["recool_capacity_kw"]),
            "mau_hw_valve_pct": 100.0 * reheat_kw / MAU["reheat_capacity_kw"],
            "mau_airflow_m3h": q_mau * 3600.0,
            "ffu_airflow_m3h": q_ffu * 3600.0,
            "ffu_face_velocity_m_s": u_ffu * FFU["rated_face_velocity_m_s"],
            "exhaust_m3h": q_exhaust * 3600.0,
        }

    def step(self, u_mau, u_ffu, q_mes_kw, particle_gen_rate, exhaust_override=None, dt_sec=60.0,
             *, door_fraction=0.0, amc_multiplier=1.0, disturbance=None):
        if any(not 0.0 <= speed <= 1.0 for speed in (u_mau, u_ffu)):
            raise ValueError("Fan commands must be in [0, 1]")
        if disturbance is None:
            disturbance = Disturbance(
                self.base_exhaust_flow if exhaust_override is None else exhaust_override,
                q_mes_kw, particle_gen_rate, self.outdoor_temp, self.outdoor_rh, door_fraction, amc_multiplier,
            )
        self.state = self.predict(u_mau, u_ffu, self.state, disturbance, dt_sec)
        self.time_min += dt_sec / 60.0
        return self.state
