"""
Baseline Controller (Traditional Conservative Cleanroom Operation)
Fans run at fixed near-maximum speeds 24/7 to guarantee contamination control.
"""

class BaselineController:
    def __init__(self, u_mau=0.95, u_ffu=1.00):
        self.u_mau = u_mau
        self.u_ffu = u_ffu

    def get_setpoints(self, sensor_data, q_mes):
        """Returns constant conservative setpoints without optimization"""
        return {
            "u_mau": self.u_mau,
            "u_ffu": self.u_ffu,
            "mode": "BASELINE_CONSTANT_SPEED",
            "safety_status": "NORMAL"
        }
