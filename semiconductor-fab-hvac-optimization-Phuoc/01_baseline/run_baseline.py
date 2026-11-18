"""Run the shared 24-hour simulation in fixed-speed mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_plots import run_daily_mode


def run_baseline_sim():
    return run_daily_mode("baseline")


if __name__ == "__main__":
    run_baseline_sim()