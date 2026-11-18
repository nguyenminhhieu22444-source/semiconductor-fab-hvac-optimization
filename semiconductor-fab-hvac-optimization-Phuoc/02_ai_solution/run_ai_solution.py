"""Run the shared 24-hour direct AI and PLC simulation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_plots import run_daily_mode


def run_ai_sim():
    return run_daily_mode("ai")


if __name__ == "__main__":
    run_ai_sim()
