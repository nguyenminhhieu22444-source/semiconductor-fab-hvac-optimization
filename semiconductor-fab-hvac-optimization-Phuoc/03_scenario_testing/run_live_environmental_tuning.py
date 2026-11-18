"""Launch the shared desktop tuning panel from this folder."""

import importlib.util
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location("_bay1_live_tuning", root / "run_live_environmental_tuning.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
run_simulation = panel.run_simulation
create_live_tuning_app = panel.create_live_tuning_app

if __name__ == "__main__":
    create_live_tuning_app()