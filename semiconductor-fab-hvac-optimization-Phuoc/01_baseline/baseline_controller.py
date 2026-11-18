"""Fixed-speed reference used to measure savings against the original strategy."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_model import CONTROL


class BaselineController:
    def __init__(self, u_mau=CONTROL["baseline_mau"], u_ffu=CONTROL["baseline_ffu"]):
        self.u_mau = u_mau
        self.u_ffu = u_ffu

    def get_setpoints(self, sensor_data=None, q_mes=None):
        return {
            "u_mau": self.u_mau,
            "u_ffu": self.u_ffu,
            "mode": "BASELINE_CONSTANT_SPEED",
            "status": "NORMAL_BASELINE",
            "safety_status": "NORMAL",
            "reasons": [],
            "production_hold": False,
        }