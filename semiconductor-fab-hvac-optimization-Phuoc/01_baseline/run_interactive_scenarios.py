"""
run_interactive_scenarios.py
Launcher for 03_scenario_testing interactive visualizer from within 01_baseline.
Allows seamless execution when the terminal is located inside 01_baseline.
"""
import os
import sys
import importlib.util

current_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = os.path.abspath(os.path.join(current_dir, "..", "03_scenario_testing"))
target_script = os.path.join(target_dir, "run_interactive_scenarios.py")

if target_dir not in sys.path:
    sys.path.insert(0, target_dir)

spec = importlib.util.spec_from_file_location("target_scenarios_module", target_script)
real_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real_mod)

for attr in dir(real_mod):
    if not attr.startswith("__"):
        globals()[attr] = getattr(real_mod, attr)

if __name__ == "__main__":
    real_mod.main()
