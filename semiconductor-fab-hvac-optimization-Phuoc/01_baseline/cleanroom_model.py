"""Compatibility import for the shared Bay 1 plant."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_model import CleanroomPlant
from bay1_scenarios import get_standard_mes_scenario

__all__ = ["CleanroomPlant", "get_standard_mes_scenario"]