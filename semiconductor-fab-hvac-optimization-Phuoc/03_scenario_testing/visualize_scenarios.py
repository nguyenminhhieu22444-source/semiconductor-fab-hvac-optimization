"""Plot energy and environmental KPIs from the exported five-scenario comparison."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bay1_model import LIMITS


def plot_scenarios_report(show=False):
    import matplotlib.pyplot as plt

    folder = Path(__file__).resolve().parent
    results = json.loads((folder / "scenarios_benchmark_results.json").read_text(encoding="utf-8"))
    rows = list(results.values())
    label = "Direct AI + PLC" if rows[0]["ai_solution"]["policy_model"] else "PLC fallback"
    modes = (("baseline", "Fixed speed"), ("pressure_reference", "Pressure reference"),
             ("physics_mpc", "Physics MPC"), ("ai_solution", label))
    positions = list(range(len(rows)))
    panel = (
        ("total_energy_kwh", "Fan electricity", "kWh", None),
        ("violation_minutes", "Time outside design limits", "minutes", None),
        ("min_dp_pa", "Minimum differential pressure", "Pa", LIMITS["dp_min"]),
        ("max_rh_pct", "Maximum relative humidity", "% RH", LIMITS["rh_max"]),
    )
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    fig.suptitle("Bay 1 operating scenarios", fontsize=16)
    for axis, (key, title, unit, limit) in zip(axes.ravel(), panel):
        for offset, (mode, label) in zip((-0.30, -0.10, 0.10, 0.30), modes):
            axis.bar([i + offset for i in positions], [row[mode][key] for row in rows], width=0.20, label=label)
        if limit is not None:
            axis.axhline(limit, color="#b43b37", linestyle="--", linewidth=1.2)
        axis.set(title=title, ylabel=unit, xticks=positions,
                 xticklabels=["Normal", "Door", "Heat", "AMC", "Standby"])
        axis.grid(axis="y", alpha=0.2)
    axes[0, 0].legend()
    fig.savefig(folder / "scenario_comparison_report.png", dpi=140)
    if show:
        plt.show()
    plt.close(fig)


if __name__ == "__main__":
    plot_scenarios_report()
