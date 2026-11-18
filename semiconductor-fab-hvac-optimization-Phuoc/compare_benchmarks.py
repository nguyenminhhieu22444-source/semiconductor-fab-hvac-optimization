"""Export the 24-hour comparison, chart and offline dashboard traces."""

import argparse

from bay1_plots import plot_daily_comparison
from bay1_simulation import export_standard_benchmark


def main(plots=True):
    baseline, ai, summary = export_standard_benchmark()
    if plots:
        try:
            plot_daily_comparison(baseline, ai, summary)
        except ModuleNotFoundError as exc:
            if exc.name != "matplotlib":
                raise
            print("Matplotlib is required to refresh the PNG. The JSON and web traces were exported.")
    print(f"Fan electricity {summary['baseline']['total_energy_kwh']:.2f} → "
          f"{summary['ai_solution']['total_energy_kwh']:.2f} kWh "
          f"({summary['savings_pct']:.2f}% against fixed speed).")
    print(f"Violations: {summary['baseline']['violation_minutes']:.0f} → "
          f"{summary['ai_solution']['violation_minutes']:.0f} minutes.")
    comparison = summary["policy_comparison"]
    ai_kpis = summary["ai_solution"]
    print(f"Direct AI model: {ai_kpis['policy_model'] or 'unavailable'}. "
          f"Compared with physics MPC: {comparison['changed_command_steps']} changed command pairs, "
          f"{comparison['fan_energy_saved_kwh']:.2f} kWh difference in savings, "
          f"{ai_kpis['ai_commands_rejected']} AI proposals rejected.")
    print("Median controller time on SAFE cycles (AI / physics MPC): "
          f"{ai_kpis['median_safe_command_time_us']} / "
          f"{summary['physics_mpc']['median_safe_command_time_us']} us.")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-plots", action="store_true", help="Export the JSON and dashboard traces only.")
    main(plots=not parser.parse_args().no_plots)
