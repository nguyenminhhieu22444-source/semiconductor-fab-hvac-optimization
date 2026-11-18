"""
AI Solution Controller:
1. Data Processing & AI State Prediction (Physics-Informed Neural Network - PINN)
2. AI Energy Optimizer (Constrained SLSQP Non-linear Optimizer)
3. PLC Safety Gatekeeper & Fail-Safe Fallback Interlock
"""
import numpy as np
from scipy.optimize import minimize
from pinn_model import CleanroomPINN

class PLCSafetyChecker:
    """
    PLC Safety Gatekeeper:
    Checks operational limits, setpoint bounds, rate-of-change, and sensor integrity.
    If unsafe -> Rejects AI commands and activates validated Fail-Safe Fallback.
    """
    def __init__(self):
        # Operational envelope bounds
        self.u_mau_min = 0.60
        self.u_mau_max = 1.00
        self.u_ffu_min = 0.45
        self.u_ffu_max = 1.00
        self.max_rate_per_min = 0.04  # Max 4% setpoint change per minute

        # Fail-Safe fallback setpoints
        self.fallback_u_mau = 0.95
        self.fallback_u_ffu = 0.95

        self.prev_u_mau = 0.90
        self.prev_u_ffu = 0.90
        self.failsafe_active = False
        self.reasons = []

    def validate_sensors(self, sensor_data):
        t = sensor_data.get("temp", 22.0)
        dp = sensor_data.get("dp", 20.0)
        c = sensor_data.get("particle_count", 200.0)

        if not (15.0 <= t <= 35.0):
            return False, f"Temperature sensor out of range ({t:.1f} C)"
        if not (0.0 <= dp <= 60.0):
            return False, f"Pressure sensor fault ({dp:.1f} Pa)"
        if c < 0 or c > 1000000:
            return False, f"Particle sensor fault ({c:.0f})"
        return True, "Sensors OK"

    def check_and_filter(self, candidate_u_mau, candidate_u_ffu, sensor_data):
        reasons = []
        is_safe = True

        # 1. Sensor fault validation
        sensor_ok, sensor_msg = self.validate_sensors(sensor_data)
        if not sensor_ok:
            is_safe = False
            reasons.append(sensor_msg)

        # 2. Operational bounds validation
        if not (self.u_mau_min <= candidate_u_mau <= self.u_mau_max):
            is_safe = False
            reasons.append(f"MAU setpoint {candidate_u_mau:.2f} violates bounds [{self.u_mau_min}, {self.u_mau_max}]")
        if not (self.u_ffu_min <= candidate_u_ffu <= self.u_ffu_max):
            is_safe = False
            reasons.append(f"FFU setpoint {candidate_u_ffu:.2f} violates bounds [{self.u_ffu_min}, {self.u_ffu_max}]")

        # 3. Rate-of-change smoothing
        d_mau = candidate_u_mau - self.prev_u_mau
        d_ffu = candidate_u_ffu - self.prev_u_ffu
        if abs(d_mau) > self.max_rate_per_min:
            candidate_u_mau = self.prev_u_mau + np.sign(d_mau) * self.max_rate_per_min
            reasons.append("MAU rate-limit clamped")
        if abs(d_ffu) > self.max_rate_per_min:
            candidate_u_ffu = self.prev_u_ffu + np.sign(d_ffu) * self.max_rate_per_min
            reasons.append("FFU rate-limit clamped")

        # 4. Critical Room Positive Pressure Protection
        current_dp = sensor_data.get("dp", 20.0)
        if current_dp < 15.8 and candidate_u_mau < self.prev_u_mau:
            is_safe = False
            reasons.append(f"Pressure warning (dP={current_dp:.1f} Pa): Throttling MAU fan rejected!")

        # Gatekeeper Decision
        if not is_safe:
            self.failsafe_active = True
            self.reasons = reasons
            u_mau_out = self.fallback_u_mau
            u_ffu_out = self.fallback_u_ffu
            status = "FAIL_SAFE_ACTIVE"
        else:
            self.failsafe_active = False
            self.reasons = reasons
            u_mau_out = candidate_u_mau
            u_ffu_out = candidate_u_ffu
            status = "SAFE"

        self.prev_u_mau = float(u_mau_out)
        self.prev_u_ffu = float(u_ffu_out)

        return {
            "u_mau": float(u_mau_out),
            "u_ffu": float(u_ffu_out),
            "status": status,
            "reasons": reasons
        }


class AIEnergyOptimizer:
    """
    AI State Predictor (PINN) & Constrained SLSQP Fan Energy Minimizer.
    """
    def __init__(self, plant_model):
        self.plant = plant_model
        self.plc = PLCSafetyChecker()
        self.pinn = CleanroomPINN(self.plant)

    def predict_state(self, u_mau, u_ffu, current_state, q_mes_kw, particle_gen_rate, dt_sec=60.0):
        """
        Uses Physics-Informed Neural Network (CleanroomPINN) forward evaluation
        incorporating thermodynamic, pressure-orifice, and HEPA mass-conservation constraints.
        """
        return self.pinn.predict(u_mau, u_ffu, current_state, q_mes_kw, particle_gen_rate, dt_sec=dt_sec)

    def optimize_setpoints(self, sensor_data, q_mes_kw, particle_gen_rate):
        def objective(u):
            p_m, p_f = self.plant.compute_fan_powers(u[0], u[1])
            return (p_m + p_f) / 1000.0

        def constraint_dp(u):
            pred = self.predict_state(u[0], u[1], sensor_data, q_mes_kw, particle_gen_rate)
            return pred["dp"] - 16.5  # >= 0

        def constraint_particles(u):
            pred = self.predict_state(u[0], u[1], sensor_data, q_mes_kw, particle_gen_rate)
            return 650.0 - pred["particle_count"]  # >= 0

        def constraint_temp_upper(u):
            pred = self.predict_state(u[0], u[1], sensor_data, q_mes_kw, particle_gen_rate)
            return 22.3 - pred["temp"]

        def constraint_temp_lower(u):
            pred = self.predict_state(u[0], u[1], sensor_data, q_mes_kw, particle_gen_rate)
            return pred["temp"] - 21.7

        constraints = [
            {'type': 'ineq', 'fun': constraint_dp},
            {'type': 'ineq', 'fun': constraint_particles},
            {'type': 'ineq', 'fun': constraint_temp_upper},
            {'type': 'ineq', 'fun': constraint_temp_lower}
        ]

        bounds = [(0.60, 1.0), (0.45, 1.0)]
        initial_guess = [self.plc.prev_u_mau, self.plc.prev_u_ffu]

        res = minimize(objective, initial_guess, method='SLSQP', bounds=bounds, constraints=constraints, options={'maxiter': 40, 'ftol': 1e-3})
        if res.success:
            cand_u_mau, cand_u_ffu = res.x
        else:
            cand_u_mau, cand_u_ffu = initial_guess

        # Submit through PLC Safety Check Gatekeeper
        plc_result = self.plc.check_and_filter(cand_u_mau, cand_u_ffu, sensor_data)
        return plc_result
