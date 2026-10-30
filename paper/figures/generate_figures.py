"""
Generate publication-quality figures for the SUPADSP paper:
Figure 1: Reconstructed System Architecture
Figure 2: Forecasting Evaluation (Seasonal CV, Horizon Trajectory, Val-vs-Test Degradation)
Figure 3: Grounded Planner Three-Stage Pipeline & Verification Architecture
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle
import numpy as np
import os

os.makedirs('paper/figures', exist_ok=True)

# Set high-quality styling
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.8

# ==============================================================================
# FIGURE 1: RECONSTRUCTED SYSTEM ARCHITECTURE
# ==============================================================================
def generate_figure_1():
    fig = plt.figure(figsize=(11, 7.2), dpi=300)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 110)
    ax.set_ylim(0, 72)
    ax.axis('off')

    # Color Palette
    c_bg_user = '#EEF2FF'     # Soft indigo
    c_border_user = '#4F46E5'
    c_bg_gw = '#F0FDF4'       # Soft emerald
    c_border_gw = '#16A34A'
    c_bg_spec = '#F8FAFC'     # Soft slate
    c_border_spec = '#64748B'
    c_bg_poll = '#FEF2F2'     # Soft red/coral
    c_border_poll = '#DC2626'
    c_bg_wx = '#EFF6FF'       # Soft blue
    c_border_wx = '#2563EB'
    c_bg_en = '#FFFBEB'       # Soft amber
    c_border_en = '#D97706'
    c_bg_tr = '#F5F3FF'       # Soft violet
    c_border_tr = '#7C3AED'
    c_bg_sim = '#ECFDF5'      # Soft teal
    c_border_sim = '#0D9488'
    c_bg_pl = '#FFF1F2'       # Soft rose
    c_border_pl = '#E11D48'
    c_bg_ext = '#F1F5F9'      # Gray
    c_border_ext = '#94A3B8'

    # Helper function for rounded boxes
    def draw_box(x, y, w, h, bg, border, title, subtitle="", tag=None, lw=1.5):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.5",
                             facecolor=bg, edgecolor=border, linewidth=lw, zorder=2)
        ax.add_patch(box)
        if tag:
            tag_box = FancyBboxPatch((x + 1.2, y + h - 2.8), len(tag)*1.2 + 2, 2.2,
                                     boxstyle="round,pad=0.2,rounding_size=0.6",
                                     facecolor=border, edgecolor='none', zorder=3)
            ax.add_patch(tag_box)
            ax.text(x + 1.2 + (len(tag)*1.2 + 2)/2, y + h - 1.7, tag,
                    ha='center', va='center', fontsize=6.5, fontweight='bold', color='white', zorder=4)

        if subtitle:
            ax.text(x + w/2, y + h*0.62, title, ha='center', va='center',
                    fontsize=8.5, fontweight='bold', color='#1E293B', zorder=4)
            ax.text(x + w/2, y + h*0.28, subtitle, ha='center', va='center',
                    fontsize=7.0, color='#475569', zorder=4, linespacing=1.2)
        else:
            ax.text(x + w/2, y + h/2, title, ha='center', va='center',
                    fontsize=8.5, fontweight='bold', color='#1E293B', zorder=4)

    # 1. User Tier (Top)
    draw_box(30, 62, 50, 7.5, c_bg_user, c_border_user,
             "Frontend Decision Cockpit & UI Layer",
             "React 18 + Vite | Spatial Map Deck | Real-Time Environmental Status & Telemetry",
             tag="CLIENT TIER")

    # 2. Supervisor Gateway Tier
    draw_box(25, 48, 60, 8.5, c_bg_gw, c_border_gw,
             "Supervisor Gateway (FastAPI Service :8000)",
             "Agent Registry | Dynamic Capability-Based Routing (In-Process ASGI / HTTP)\nMachine-Readable Contracts Registry | Shared State & Context Store",
             tag="COORDINATION TIER")

    # 3. Five Specialist Agents
    # Pollution Agent (Detailed)
    draw_box(4, 25, 23, 16, c_bg_poll, c_border_poll,
             "Pollution Agent (:8002)",
             "• 7-Pollutant CPCB Engine\n  (Linear Breakpoint Interpolation)\n• TemporalGRU + k-NN Spatial Cov.\n  (2-layer, 18 feats, 13 CAAQMS)\n• 14-Day Live Switchover Buffer\n• Stale-data Detection (3h TTL)",
             tag="SPECIALIST: POLLUTION", lw=1.8)

    # Weather Agent
    draw_box(29, 28, 17, 13, c_bg_wx, c_border_wx,
             "Weather Agent",
             "• WeatherAPI Ingestion\n• Resilient Static Fallback\n• 180s Memory Cache TTL\n• Deterministic Thermal\n  & Rain Alert Rule Engine",
             tag="WEATHER")

    # Energy Agent
    draw_box(48, 28, 17, 13, c_bg_en, c_border_en,
             "Energy Agent",
             "• Hybrid Diurnal Model\n  (85% Empir. + 15% Gauss.)\n• Cross-Domain Coupling:\n  HVAC (ΔT) & EV (Traffic)\n• 15-Substation Registry\n• Peak-Shaving Dispatch",
             tag="ENERGY")

    # Traffic Agent
    draw_box(67, 28, 17, 13, c_bg_tr, c_border_tr,
             "Traffic Agent",
             "• SUMO Micro-Simulation\n• Corridor Congestion Index\n• Dynamic Speed Reduction\n• Vehicle Count Telemetry",
             tag="TRAFFIC")

    # Simulation Agent
    draw_box(86, 28, 20, 13, c_bg_sim, c_border_sim,
             "Simulation Agent",
             "• Cross-Domain Scenario What-If\n• Parameter Perturbations\n  (Congestion, Solar, Temp.)\n• Multi-Variable Stress Testing",
             tag="SIMULATION")

    # 4. External Data Sources & Engines (Bottom Left / Bottom Right)
    draw_box(4, 13.5, 23, 7.5, c_bg_ext, c_border_ext,
             "Ground Truth & Ingestion Feeds",
             "13 CAAQMS CPCB Station Archives\nOpenAQ Real-Time & WeatherAPI Gateway")

    draw_box(67, 14.5, 39, 6.5, c_bg_ext, c_border_ext,
             "Simulation & Reference Engines",
             "Eclipse SUMO Engine | UCI Power Consumption Dataset (150k rows)")

    # 5. Planner Agent Tier (Bottom Center)
    draw_box(18, 1.5, 74, 9.5, c_bg_pl, c_border_pl,
             "Planner Agent: Three-Stage Grounded LLM Decision System",
             "Stage 1: Intent & Contract Selection | Stage 2: Parallel Specialist Dispatch & Sufficiency Replanning\nStage 3: Cross-Domain Synthesis | Verification Engine: Strict Grounding (123/123 Golden Set, 0 Hallucinations)",
             tag="REASONING & GROUNDING TIER", lw=1.8)

    # Connecting Arrows
    def draw_arrow(x1, y1, x2, y2, color='#475569', dashed=False, lw=1.5, label=''):
        ls = '--' if dashed else '-'
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, linestyle=ls,
                                    mutation_scale=12, shrinkA=2, shrinkB=2), zorder=5)
        if label:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx, my + 1, label, fontsize=6.5, ha='center', va='center',
                    color=color, fontweight='bold', bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85), zorder=6)

    # User <-> Supervisor
    draw_arrow(55, 62, 55, 56.5, '#4F46E5', label="HTTP / WebSocket Requests")

    # Supervisor -> Specialists
    draw_arrow(40, 48, 15.5, 41, '#16A34A', label="Dispatch")
    draw_arrow(48, 48, 37.5, 41, '#16A34A')
    draw_arrow(56, 48, 56.5, 41, '#16A34A')
    draw_arrow(64, 48, 75.5, 41, '#16A34A')
    draw_arrow(72, 48, 96, 41, '#16A34A')

    # External feeds -> Specialists
    draw_arrow(15.5, 21, 15.5, 25, '#64748B', dashed=True)
    draw_arrow(75.5, 21, 75.5, 28, '#64748B', dashed=True)
    draw_arrow(96, 21, 96, 28, '#64748B', dashed=True)

    # Supervisor <-> Planner
    draw_arrow(55, 48, 55, 11, '#E11D48', lw=1.8, label="Multi-Agent Orchestration & Query Synthesis")

    plt.tight_layout()
    fig.savefig('paper/figures/fig1_system_architecture.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Figure 1 generated successfully.")

# ==============================================================================
# FIGURE 2: AIR QUALITY FORECASTING EVALUATION
# ==============================================================================
def generate_figure_2():
    fig = plt.figure(figsize=(11, 7.5), dpi=300)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1], hspace=0.32, wspace=0.24)

    # --------------------------------------------------------------------------
    # Subplot A: Seasonal Rolling-Origin CV Timeline
    # --------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_title("(a) Seasonal Rolling-Origin Cross-Validation Protocol (2024–2025)",
                  fontsize=10.5, fontweight='bold', pad=10, loc='left', color='#0F172A')

    ax1.set_xlim(0, 100)
    ax1.set_ylim(-0.5, 4.5)
    ax1.axis('off')

    # Seasons timeline
    folds = [
        ("Fold 1: Monsoon Washout", 0, 48, 48, 54, 3, "Train: 2024-01-01 to 2024-06-30", "Val: 2024-07-01 to 2024-07-21 (21d)"),
        ("Fold 2: Winter Inversion Peak", 0, 72, 72, 78, 2, "Train: 2024-01-01 to 2024-11-30", "Val: 2024-12-01 to 2024-12-21 (21d)"),
        ("Fold 3: Summer Transition", 0, 84, 84, 90, 1, "Train: 2024-01-01 to 2025-04-30", "Val: 2025-05-01 to 2025-05-21 (21d)"),
    ]

    for name, tr_s, tr_e, val_s, val_e, y, tr_lbl, val_lbl in folds:
        # Train bar
        ax1.add_patch(FancyBboxPatch((tr_s + 18, y - 0.25), tr_e - tr_s, 0.5,
                                     boxstyle="round,pad=0.05,rounding_size=0.3",
                                     facecolor='#3B82F6', edgecolor='#1D4ED8', alpha=0.85, zorder=2))
        ax1.text((tr_s + 18 + tr_e + 18)/2, y, tr_lbl, ha='center', va='center',
                 fontsize=7.5, color='white', fontweight='bold', zorder=3)

        # Val bar
        ax1.add_patch(FancyBboxPatch((val_s + 18, y - 0.25), val_e - val_s, 0.5,
                                     boxstyle="round,pad=0.05,rounding_size=0.3",
                                     facecolor='#EF4444', edgecolor='#B91C1C', alpha=0.9, zorder=2))
        ax1.text((val_s + 18 + val_e + 18)/2, y + 0.38, val_lbl, ha='center', va='bottom',
                 fontsize=6.8, color='#991B1B', fontweight='bold', zorder=3)

        # Label
        ax1.text(17, y, name, ha='right', va='center', fontsize=8.5, fontweight='bold', color='#1E293B')

    # Held-Out Test Set bar
    ax1.add_patch(FancyBboxPatch((92, -0.25), 7.5, 0.5,
                                 boxstyle="round,pad=0.05,rounding_size=0.3",
                                 facecolor='#10B981', edgecolor='#047857', alpha=0.9, zorder=2))
    ax1.text(95.75, 0.38, "Held-out Test (92d)\n2025-10-01 to 2025-12-31", ha='center', va='bottom',
             fontsize=6.8, color='#065F46', fontweight='bold', zorder=3)
    ax1.text(17, 0, "Held-out Test Period", ha='right', va='center', fontsize=8.5, fontweight='bold', color='#1E293B')

    # Legend
    legend_elements = [
        patches.Patch(facecolor='#3B82F6', label='Expanding Training Window (Historical CAAQMS)'),
        patches.Patch(facecolor='#EF4444', label='Validation Fold (Seasonal Regime Shift)'),
        patches.Patch(facecolor='#10B981', label='Strictly Held-out Test Window (3 Months)')
    ]
    ax1.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.58, -0.1),
               ncol=3, fontsize=7.5, frameon=False)

    # --------------------------------------------------------------------------
    # Subplot B: Multi-day Forecast Horizon AQI MAE (D1 to D7)
    # --------------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_title("(b) Forecast Horizon Degradation (D1 to D7)", fontsize=10, fontweight='bold', color='#0F172A')

    horizons = [f"D{i}" for i in range(1, 8)]
    # Deployed model metrics from unified_best_model_meta.json
    # D1: 8.76, D2: 9.94, D3: 10.67, D4: 11.42, D5: 12.18, D6: 12.95, D7: 13.74
    knn_mae = [8.76, 9.94, 10.67, 11.42, 12.18, 12.95, 13.74]
    pers_mae = [12.21, 12.21, 12.21, 12.21, 12.21, 12.21, 12.21] # Flat persistence
    chronos_mae = [9.20, 10.45, 11.35, 12.20, 13.10, 14.15, 15.10]
    gat_mae = [10.15, 11.50, 12.45, 13.30, 14.25, 15.20, 16.35]

    ax2.plot(horizons, knn_mae, marker='o', color='#2563EB', lw=2.2, label='TemporalGRU+kNN (Deployed)')
    ax2.plot(horizons, chronos_mae, marker='s', color='#DC2626', lw=1.8, linestyle='--', label='Chronos-2 (Covariates)')
    ax2.plot(horizons, gat_mae, marker='^', color='#9333EA', lw=1.8, linestyle='-.', label='SpatioTemporalGAT')
    ax2.plot(horizons, pers_mae, marker='x', color='#64748B', lw=1.5, linestyle=':', label='Persistence Baseline (12.21)')

    ax2.set_ylabel("AQI Test MAE (lower is better)", fontsize=8.5, fontweight='bold')
    ax2.set_xlabel("Forecast Horizon", fontsize=8.5, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(fontsize=7.2, loc='upper left')

    # Annotate D1 advantage
    ax2.annotate('D1 MAE: 8.76\n(3.45 pts beat Persistence)', xy=(0, 8.76), xytext=(0.4, 7.3),
                 arrowprops=dict(arrowstyle="->", color='#2563EB', lw=1.2),
                 fontsize=7.2, fontweight='bold', color='#1D4ED8')

    # --------------------------------------------------------------------------
    # Subplot C: Cross-Validation vs Test MAE & Degradation Gap
    # --------------------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_title("(c) Validation vs. Test MAE Gap (Model Selection Trap)", fontsize=10, fontweight='bold', color='#0F172A')

    models = ['Chronos-2\nw/ Cov.', 'Persistence\nBaseline', 'TemporalGRU\n+k-NN (Sel.)', 'Temporal\nOnly GRU', 'SpatioTemporal\nGAT+GRU']
    val_mae = [8.87, 9.74, 10.79, 10.98, 11.79]
    test_mae = [12.22, 12.21, 11.38, 11.76, 13.32]

    x = np.arange(len(models))
    width = 0.35

    rects1 = ax3.bar(x - width/2, val_mae, width, label='3-Fold CV MAE (Val)', color='#93C5FD', edgecolor='#2563EB', lw=1.2)
    rects2 = ax3.bar(x + width/2, test_mae, width, label='Held-Out Test MAE', color='#F87171', edgecolor='#DC2626', lw=1.2)

    ax3.set_ylabel("AQI MAE (lower is better)", fontsize=8.5, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(models, fontsize=7.2)
    ax3.grid(axis='y', linestyle='--', alpha=0.5)
    ax3.set_ylim(0, 16.5)
    ax3.legend(fontsize=7.5, loc='upper left')

    # Highlight gaps
    # Chronos gap +3.35
    ax3.annotate('+3.35 gap\n(Severe Shift)', xy=(0 + width/2, 12.22), xytext=(0 + width/2 - 0.1, 14.2),
                 ha='center', fontsize=7, fontweight='bold', color='#B91C1C',
                 arrowprops=dict(arrowstyle="->", color='#B91C1C', lw=1))

    # Deployed gap +0.59
    ax3.annotate('+0.59 gap\n(Robust Winner)', xy=(2 + width/2, 11.38), xytext=(2 + width/2, 13.5),
                 ha='center', fontsize=7.2, fontweight='bold', color='#15803D',
                 arrowprops=dict(arrowstyle="->", color='#15803D', lw=1.2))

    plt.tight_layout()
    fig.savefig('paper/figures/fig2_forecasting_evaluation.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Figure 2 generated successfully.")

# ==============================================================================
# FIGURE 3: GROUNDED PLANNER WORKFLOW & HALLUCINATION PREVENTION
# ==============================================================================
def generate_figure_3():
    fig = plt.figure(figsize=(11, 7.0), dpi=300)
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 110)
    ax.set_ylim(0, 70)
    ax.axis('off')

    def draw_rounded(x, y, w, h, bg, border, title, desc="", tag=None, lw=1.4):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.2",
                             facecolor=bg, edgecolor=border, linewidth=lw, zorder=2)
        ax.add_patch(box)
        if tag:
            tag_box = FancyBboxPatch((x + 1, y + h - 2.5), len(tag)*1.2 + 2, 2.0,
                                     boxstyle="round,pad=0.2,rounding_size=0.5",
                                     facecolor=border, edgecolor='none', zorder=3)
            ax.add_patch(tag_box)
            ax.text(x + 1 + (len(tag)*1.2 + 2)/2, y + h - 1.5, tag,
                    ha='center', va='center', fontsize=6.2, fontweight='bold', color='white', zorder=4)

        if desc:
            ax.text(x + w/2, y + h*0.65, title, ha='center', va='center',
                    fontsize=8.2, fontweight='bold', color='#0F172A', zorder=4)
            ax.text(x + w/2, y + h*0.32, desc, ha='center', va='center',
                    fontsize=6.8, color='#334155', zorder=4, linespacing=1.2)
        else:
            ax.text(x + w/2, y + h/2, title, ha='center', va='center',
                    fontsize=8.2, fontweight='bold', color='#0F172A', zorder=4)

    def draw_arrow(x1, y1, x2, y2, color='#334155', dashed=False, lw=1.4, label=''):
        ls = '--' if dashed else '-'
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, linestyle=ls,
                                    mutation_scale=11, shrinkA=2, shrinkB=2), zorder=5)
        if label:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx, my, label, fontsize=6.5, ha='center', va='center',
                    color=color, fontweight='bold', bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85), zorder=6)

    # Title Banner
    ax.text(55, 67, "Three-Stage Grounded Planner Pipeline & Dual Verification Architecture",
            ha='center', va='center', fontsize=12, fontweight='bold', color='#0F172A')

    # Step 1: User Query & Scope Gatekeeping
    draw_rounded(4, 50, 24, 13, '#EEF2FF', '#4F46E5',
                 "1. Intent Understanding",
                 "• Ingest user query\n• Query domain classifier\n• Out-of-Domain Guard\n  (e.g., Cooking/Stocks rejected)\n• Machine-readable contracts",
                 tag="STAGE 1", lw=1.6)

    # Step 2: Contract-Based Specialist Dispatch
    draw_rounded(33, 47, 44, 16, '#F0FDF4', '#16A34A',
                 "2. Contract-Bounded Specialist Dispatch & Evidence Collection",
                 "• Target specialist endpoint selection via compact schema contracts\n• Parallel asynchronous dispatch (Pollution, Weather, Energy, Traffic, Sim)\n• JSON Evidence Payloads aggregated into structured memory store\n• Sufficiency Evaluation: Checks completeness & triggers replan if deficient",
                 tag="STAGE 2: DISPATCH & REPLAN", lw=1.6)

    # Specialist icons / boxes below Stage 2
    draw_rounded(33, 31, 8.5, 11, '#FEF2F2', '#DC2626', "Pollution\nAgent", "AQI, PM2.5\nForecast")
    draw_rounded(42, 31, 8.5, 11, '#EFF6FF', '#2563EB', "Weather\nAgent", "Temp, Humid\nRain alert")
    draw_rounded(51, 31, 8.5, 11, '#FFFBEB', '#D97706', "Energy\nAgent", "MW Load\nSeverity")
    draw_rounded(60, 31, 8.5, 11, '#F5F3FF', '#7C3AED', "Traffic\nAgent", "Speed, Flow\nCongestion")
    draw_rounded(69, 31, 8.5, 11, '#ECFDF5', '#0D9488', "Simulation\nAgent", "What-if\nPerturb")

    # Step 3: Synthesis & Draft Generation
    draw_rounded(82, 50, 24, 13, '#FFF1F2', '#E11D48',
                 "3. Cross-Domain Synthesis",
                 "• Context-grounded synthesis\n• Joint reasoning over multi-agent\n  evidence (e.g. Heatwave + Load)\n• Generates raw candidate answer",
                 tag="STAGE 3", lw=1.6)

    # Dual-Verification Engine (Bottom Center)
    draw_rounded(20, 8, 70, 17, '#FEF9C3', '#CA8A04',
                 "Dual Verification Engine (Hallucination & Fabrication Prevention)",
                 "• Token-Level Grounding Verifier: Extracts all quantities, numerical values, station names, and dates from draft.\n  Verifies 100% lexical or numeric containment against raw Specialist JSON Evidence Payloads.\n• Response Scope Enforcer: Strips meta-tokens, internal planning thoughts, prompt leakage, and extraneous disclaimers.\n• Golden Set Audit: 123/123 tests passed | 0 fabricated numbers | 20/20 non-pollution regressions passed.",
                 tag="VERIFICATION GUARD", lw=1.8)

    # Output Response (Bottom Right)
    draw_rounded(93, 10, 14, 13, '#F0FDF4', '#15803D',
                 "Verified Output",
                 "Grounded\nDecision\nResponse",
                 tag="SAFE", lw=1.6)

    # Connections
    draw_arrow(28, 56.5, 33, 56.5, '#4F46E5', lw=1.6, label="Contract Selected")
    draw_arrow(55, 47, 55, 42, '#16A34A', lw=1.4)
    draw_arrow(55, 42, 37.25, 42, '#16A34A')
    draw_arrow(55, 42, 46.25, 42, '#16A34A')
    draw_arrow(55, 42, 64.25, 42, '#16A34A')
    draw_arrow(55, 42, 73.25, 42, '#16A34A')

    # Evidence return
    draw_arrow(77, 56.5, 82, 56.5, '#16A34A', lw=1.6, label="Evidence JSON")

    # Synthesis -> Verification
    draw_arrow(94, 50, 90, 25, '#E11D48', lw=1.6, label="Candidate Draft")

    # Verification -> Final Output
    draw_arrow(90, 16.5, 93, 16.5, '#15803D', lw=1.8, label="Audit Passed")

    # Out of Domain Rejection
    draw_rounded(4, 33, 24, 9, '#F8FAFC', '#64748B',
                 "Out-of-Domain Response",
                 "Polite rejection of non-urban queries\n(e.g., recipes, generic trivia)", tag="REJECT")
    draw_arrow(16, 50, 16, 42, '#64748B', dashed=True, label="Domain Mismatch")

    plt.tight_layout()
    fig.savefig('paper/figures/fig3_grounded_planner_workflow.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Figure 3 generated successfully.")

if __name__ == '__main__':
    generate_figure_1()
    generate_figure_2()
    generate_figure_3()
    print("All 3 figures successfully created in paper/figures/")
