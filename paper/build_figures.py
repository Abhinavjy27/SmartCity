"""Generate Overleaf-ready figures from project evidence.

Only local files are read.  Forecast values come from the unified model
metadata artifact; the diagrams describe the implemented component roles.
"""
from pathlib import Path
import json
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

ROOT = Path(__file__).parent
OUT = ROOT / "figures"
META = ROOT.parent / "backend" / "agents" / "pollution_agent" / "unified_forecast" / "artifacts" / "unified_best_model_meta.json"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titleweight": "bold"})


def save(fig, stem):
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def box(ax, x, y, w, h, title, body, color, fs=8.5):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.025,rounding_size=0.035",
                       facecolor=color, edgecolor="#334155", linewidth=1.0)
    ax.add_patch(p)
    ax.text(x + w/2, y + h*0.68, title, ha="center", va="center", weight="bold", fontsize=fs)
    ax.text(x + w/2, y + h*0.32, body, ha="center", va="center", fontsize=7.1,
            color="#334155", linespacing=1.25)


def arrow(ax, a, b, color="#475569", dashed=False, rad=0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11,
                                 linewidth=1.25, linestyle="--" if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}", color=color))


def frame(ax, title, lim=(0, 12, 0, 8)):
    ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[2], lim[3]); ax.axis("off")
    ax.text((lim[0]+lim[1])/2, lim[3]-.18, title, ha="center", va="top",
            fontsize=14, weight="bold", color="#0f172a")


def figure1():
    fig, ax = plt.subplots(figsize=(11.5, 7)); frame(ax, "SUPADSP system architecture")
    box(ax, 3.7, 6.35, 4.6, .72, "Decision cockpit", "React/Vite maps, dashboards, planning UI", "#dbeafe", 9)
    box(ax, 3.0, 5.05, 6.0, .82, "LLM planner", "intent gate → selects specialist agents → synthesis / scope check", "#ffe4e6", 9)
    box(ax, .55, 3.35, 2.15, 1.05, "Pollution agent", "CPCB AQI + trained GRU/GAT", "#fee2e2")
    box(ax, 3.25, 3.35, 2.15, 1.05, "Weather agent", "provider ingestion + fallback", "#dbeafe")
    box(ax, 5.95, 3.35, 2.15, 1.05, "Energy agent", "deterministic profile / rules", "#fef3c7")
    box(ax, 8.65, 3.35, 2.15, 1.05, "Traffic / simulation", "SUMO + scenario logic", "#ede9fe")
    box(ax, 3.0, 1.45, 6.0, .82, "FastAPI supervisor gateway", "contracts, context, dispatch, response assembly", "#dcfce7", 9)
    box(ax, .85, .25, 3.25, .72, "Data and provider inputs", "CPCB archives • weather feed • UCI profile • OSM/SUMO", "#f1f5f9", 7.8)
    box(ax, 7.9, .25, 3.25, .72, "Evidence outputs", "JSON payloads • forecasts • deterministic results • simulations", "#ccfbf1", 7.8)
    arrow(ax, (6, 6.35), (6, 5.87), "#2563eb")
    arrow(ax, (3.6, 5.05), (1.63, 4.4), "#16a34a"); arrow(ax, (4.8, 5.05), (4.33, 4.4), "#16a34a")
    arrow(ax, (6.4, 5.05), (7.03, 4.4), "#16a34a"); arrow(ax, (7.7, 5.05), (9.73, 4.4), "#16a34a")
    for x in [1.63, 4.33, 7.03, 9.73]: arrow(ax, (x, 3.35), (x, 2.27), "#64748b", dashed=True)
    arrow(ax, (4.65, 1.45), (2.5, .97), "#64748b", dashed=True); arrow(ax, (7.35, 1.45), (9.5, .97), "#64748b", dashed=True)
    ax.text(6, 7.35, "Solid: planner selection and gateway dispatch   Dashed: data/evidence flow", ha="center", fontsize=8, color="#475569")
    save(fig, "fig1_system_architecture")


def figure2():
    meta = json.loads(META.read_text(encoding="utf-8"))
    cv = meta["validation_summary"]; test = meta["test_evaluation_single_pass"]
    names = ["Temporal-only\nGRU", "GAT-GRU", "kNN-covariate\nGRU", "Chronos-2", "Persistence", "Seasonal\nnaive"]
    keys = ["TemporalOnlyGRU", "SpatialTemporalGATGRU_Weighted", "TemporalGRU_KNNCovariate", "Chronos2_Covariates", "Persistence_Baseline", "SeasonalNaive_Baseline"]
    cvv = [cv[k]["MAE_mean"] for k in keys]; tv = [test[k]["AQI_MAE"] for k in keys]
    horizons = list(meta["winner_test_metrics"]["by_horizon"])
    hmae = [meta["winner_test_metrics"]["by_horizon"][h]["AQI_MAE"] for h in horizons]
    hrmse = [meta["winner_test_metrics"]["by_horizon"][h]["AQI_RMSE"] for h in horizons]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.9), constrained_layout=True)
    ax = axes[0]; x = np.arange(len(names)); width = .36
    b1 = ax.bar(x-width/2, cvv, width, color="#93c5fd", edgecolor="#2563eb", label="3-fold CV MAE")
    b2 = ax.bar(x+width/2, tv, width, color="#fca5a5", edgecolor="#dc2626", label="held-out test MAE")
    ax.set_xticks(x, names); ax.set_ylabel("AQI MAE (lower is better)"); ax.set_title("(a) Cross-validation vs held-out test")
    ax.grid(axis="y", alpha=.25); ax.legend(frameon=False, fontsize=8)
    for bars in [b1, b2]:
        for b in bars: ax.text(b.get_x()+b.get_width()/2, b.get_height()+.18, f"{b.get_height():.2f}", ha="center", fontsize=7)
    ax = axes[1]; x = np.arange(len(horizons))
    ax.plot(x, hmae, marker="o", lw=2, color="#2563eb", label="MAE")
    ax.plot(x, hrmse, marker="s", lw=2, color="#d97706", label="RMSE")
    ax.set_xticks(x, horizons); ax.set_xlabel("Deployment forecast horizon"); ax.set_ylabel("AQI error")
    ax.set_title("(b) Deployed kNN-covariate GRU by horizon"); ax.grid(alpha=.25); ax.legend(frameon=False, fontsize=8)
    ax.text(0, -.28, "Directional accuracy is reported in the metadata but omitted here; no chance baseline is assumed.", transform=ax.transAxes, fontsize=7.5, color="#475569")
    save(fig, "fig2_forecasting_evaluation")


def figure3():
    fig, ax = plt.subplots(figsize=(11.5, 4.8)); frame(ax, "Evidence-grounded planner workflow", (0, 12, 0, 5))
    stages = [("1  Intent gate", "classify domain\nand scope", "#dbeafe"), ("2  Agent selection", "LLM planner chooses\ncapabilities", "#dcfce7"), ("3  Gateway dispatch", "typed contracts +\nshared context", "#fef3c7"), ("4  Evidence check", "sufficiency; replan\nwhen needed", "#ffe4e6"), ("5  Verify / respond", "numeric + scope\nchecks", "#ede9fe")]
    xs = [.25, 2.65, 5.05, 7.45, 9.85]
    for x, (t, b, c) in zip(xs, stages): box(ax, x, 2.25, 2.0, 1.15, t, b, c, 8.0)
    for x in xs[:-1]: arrow(ax, (x+2.0, 2.82), (x+2.4, 2.82))
    box(ax, .8, .55, 2.75, .82, "Missing evidence", "bounded answer or replan", "#f1f5f9", 8)
    box(ax, 4.6, .55, 2.75, .82, "Agent payloads", "source labels + typed values", "#f1f5f9", 8)
    box(ax, 8.4, .55, 2.75, .82, "Decision support", "recommendation with limits", "#f1f5f9", 8)
    arrow(ax, (1.8, 2.25), (2.1, 1.37), "#64748b", True); arrow(ax, (6.05, 2.25), (5.95, 1.37), "#64748b", True); arrow(ax, (10.85, 2.25), (9.8, 1.37), "#64748b", True)
    ax.text(6, .12, "The pipeline supports expert decisions; it does not provide universal hallucination guarantees or replace statutory approval.", ha="center", fontsize=8, color="#475569")
    save(fig, "fig3_grounded_planner_workflow")


def figure4():
    fig, ax = plt.subplots(figsize=(11.5, 6.2)); frame(ax, "Evidence provenance across SUPADSP", (0, 12, 0, 7))
    box(ax, .55, 4.25, 2.55, 1.25, "Learned evidence", "locally trained GRU/GAT\nAQI forecast + metrics", "#dbeafe")
    box(ax, 3.35, 4.25, 2.55, 1.25, "Provider evidence", "weather API ingestion\nplus deterministic fallback", "#dcfce7")
    box(ax, 6.15, 4.25, 2.55, 1.25, "Deterministic evidence", "CPCB sub-indices\nenergy rules / profiles", "#fef3c7")
    box(ax, 8.95, 4.25, 2.55, 1.25, "Simulation evidence", "SUMO scenarios\nwhat-if outputs", "#ede9fe")
    box(ax, 2.1, 2.0, 7.8, 1.05, "Evidence payload boundary", "source label • timestamp/context • units • uncertainty/limitations • machine-readable result", "#f1f5f9", 8.5)
    box(ax, 3.3, .35, 5.4, .92, "Planner response", "synthesis preserves provenance and distinguishes observed, computed, and simulated claims", "#ffe4e6", 8)
    for x in [1.83, 4.63, 7.43, 10.23]: arrow(ax, (x, 4.25), (x if x < 6 else 7.7, 3.05), "#64748b", True)
    arrow(ax, (6, 2.0), (6, 1.27), "#e11d48")
    ax.text(6, 6.65, "Different epistemic status is retained through the gateway and planner", ha="center", fontsize=9, color="#475569")
    save(fig, "fig4_evidence_provenance")


if __name__ == "__main__":
    if not META.exists(): raise FileNotFoundError(META)
    figure1(); figure2(); figure3(); figure4()
    print(f"Wrote PNG and PDF figures to {OUT}")
