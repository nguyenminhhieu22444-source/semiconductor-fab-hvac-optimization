"""Compatibility import for the shared Bay 1 scenarios."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_scenarios import (
    generate_scenario_1_standard,
    generate_scenario_2_door_breach,
    generate_scenario_3_summer_heatwave,
    generate_scenario_4_chemical_amc_surge,
    generate_scenario_5_weekend_maintenance,
    get_all_scenarios,
)

__all__ = [
    "generate_scenario_1_standard",
    "generate_scenario_2_door_breach",
    "generate_scenario_3_summer_heatwave",
    "generate_scenario_4_chemical_amc_surge",
    "generate_scenario_5_weekend_maintenance",
    "get_all_scenarios",
]