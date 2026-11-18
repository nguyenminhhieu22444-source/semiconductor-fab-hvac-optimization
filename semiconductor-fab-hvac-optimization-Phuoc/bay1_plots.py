"""Plots for the shared simulation without requiring a desktop backend."""

from bay1_model import LIMITS
from bay1_scenarios import generate_benchmark_day
from bay1_simulation import ROOT, simulate_single_mode, write_json


TRACE_PANELS = (
    ("p_total_kw", "Fan electric power", "kW", ()),
    ("energy_kwh", "Cumulative fan electricity", "kWh", ()),
    ("dp", "Room differential pressure", "Pa", (LIMITS["dp_min"], LIMITS["dp_max"])),
    ("temp", "Room temperature", "°C", (LIMITS["temp_min"], LIMITS["temp_max"])),
    ("rh", "Room relative humidity", "% RH", (LIMITS["rh_min"], LIMITS["rh_max"])),
    ("particle_count", "Particles ≥0.1 µm", "particles/m³", (LIMITS["particles_01_max"],)),
    ("particles_05", "Particles ≥0.5 µm", "particles/m³", (LIMITS["particles_05_max"],)),
    ("amc_nh3", "Ammonia", "ppb", (LIMITS["nh3_max"],)),
)


def populate_daily_plot(figure, traces):
    axes = figure.subplots(4, 2, sharex=True).ravel()
    for axis, (key, title, unit, limits) in zip(axes, TRACE_PANELS):
        for name, trace in traces:
            axis.plot(trace["time_hr"], trace[key], label=name, linewidth=1.4)
        for limit in limits:
            axis.axhline(limit, linestyle="--", color="#b43b37", linewidth=0.9)
        axis.set(title=title, ylabel=unit, xlim=(0, 24))
        if key in {"particle_count", "particles_05"}:
            axis.set_yscale("symlog", linthresh=max(limits) / 5)
        axis.grid(alpha=0.2)
    axes[0].legend(loc="best")
    for axis in axes[-2:]:
        axis.set_xlabel("Simulated hour")


def plot_daily_comparison(baseline, ai, summary):
    from matplotlib.figure import Figure

    label = ai_mode_label(summary["ai_solution"])
    fig = Figure(figsize=(13, 11), layout="constrained")
    fig.suptitle(
        f"Bay 1  |  Fixed speed vs {label}  |  "
        f"{summary['savings_pct']:.1f}% fan electricity reduction"
    )
    populate_daily_plot(fig, [("Fixed speed", baseline), (label, ai)])
    fig.savefig(ROOT / "comparison_summary.png", dpi=135)


def run_daily_mode(mode):
    from matplotlib.figure import Figure

    trace, kpis = simulate_single_mode(generate_benchmark_day(), mode)
    label, directory, stem = {
        "baseline": ("Fixed speed", "01_baseline", "baseline"),
        "ai": (ai_mode_label(kpis), "02_ai_solution", "ai"),
    }[mode]
    write_json(ROOT / directory / f"{stem}_kpis.json", kpis)
    fig = Figure(figsize=(12, 10), layout="constrained")
    fig.suptitle(f"Bay 1  |  {label}  |  {kpis['violation_minutes']:.0f} minutes outside design limits")
    populate_daily_plot(fig, [(label, trace)])
    fig.savefig(ROOT / directory / f"{stem}_results.png", dpi=135)
    print(f"{label}: {kpis['total_energy_kwh']:.2f} kWh fan electricity")
    return trace, kpis


def ai_mode_label(kpis):
    if not kpis.get("policy_model"):
        return "PLC fallback"
    return "AI + PINN + PLC" if kpis.get("pinn_model") else "Direct AI + PLC"
