"""Build a self-contained research-paper PDF without requiring LaTeX.

The PDF is generated from the verified manuscript facts in the repository and
the reconstructed figures in paper/figures. It intentionally avoids credentials
and does not make claims that are not supported by the implementation.
"""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Spacer, PageBreak, Image, Table, TableStyle, KeepTogether)

ROOT = Path(__file__).parent
OUT = ROOT / "SUPADSP_research_paper.pdf"
FIG = ROOT / "figures"

font_dir = Path(__import__('matplotlib').get_data_path()) / 'fonts/ttf'
pdfmetrics.registerFont(TTFont('DejaVu', str(font_dir / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', str(font_dir / 'DejaVuSans-Bold.ttf')))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='PaperTitle', parent=styles['Title'], fontName='DejaVu-Bold', fontSize=18, leading=22, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a'), spaceAfter=8))
styles.add(ParagraphStyle(name='Authors', parent=styles['Normal'], fontName='DejaVu', fontSize=9, leading=12, alignment=TA_CENTER, textColor=colors.HexColor('#475569'), spaceAfter=12))
styles.add(ParagraphStyle(name='Abstract', parent=styles['Normal'], fontName='DejaVu', fontSize=8.6, leading=11.5, alignment=TA_JUSTIFY, leftIndent=10*mm, rightIndent=10*mm, spaceAfter=10))
styles.add(ParagraphStyle(name='H1x', parent=styles['Heading1'], fontName='DejaVu-Bold', fontSize=12.5, leading=15, textColor=colors.HexColor('#0f172a'), spaceBefore=9, spaceAfter=5))
styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], fontName='DejaVu-Bold', fontSize=10.2, leading=12, textColor=colors.HexColor('#1e3a8a'), spaceBefore=6, spaceAfter=3))
styles.add(ParagraphStyle(name='Bodyx', parent=styles['BodyText'], fontName='DejaVu', fontSize=8.3, leading=11, alignment=TA_JUSTIFY, spaceAfter=5))
styles.add(ParagraphStyle(name='Smallx', parent=styles['BodyText'], fontName='DejaVu', fontSize=7.2, leading=9, alignment=TA_LEFT, textColor=colors.HexColor('#334155')))
styles.add(ParagraphStyle(name='Captionx', parent=styles['BodyText'], fontName='DejaVu', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#475569'), spaceBefore=3, spaceAfter=7))


def P(text, style='Bodyx'):
    return Paragraph(text, styles[style])


def table(data, widths, header=True, font=6.8):
    cooked = []
    for row in data:
        cooked.append([Paragraph(str(x), ParagraphStyle('cell', parent=styles['Smallx'], fontSize=font, leading=font+1.8)) for x in row])
    t = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    cmds = [('GRID', (0,0), (-1,-1), .35, colors.HexColor('#cbd5e1')), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING',(0,0),(-1,-1),4), ('RIGHTPADDING',(0,0),(-1,-1),4), ('TOPPADDING',(0,0),(-1,-1),3), ('BOTTOMPADDING',(0,0),(-1,-1),3)]
    if header:
        cmds += [('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dbeafe')), ('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#0f172a'))]
    t.setStyle(TableStyle(cmds)); return t


def fig(name, width, caption):
    im = Image(str(FIG / name), width=width, height=width*0.57)
    return [im, P(caption, 'Captionx')]


def footer(canvas, doc):
    canvas.saveState(); canvas.setFont('DejaVu', 7); canvas.setFillColor(colors.HexColor('#64748b'))
    canvas.drawString(18*mm, 10*mm, 'SUPADSP | Multi-domain evidence-grounded urban decision support')
    canvas.drawRightString(A4[0]-18*mm, 10*mm, f'Page {doc.page}')
    canvas.restoreState()


def build():
    frame = Frame(17*mm, 16*mm, A4[0]-34*mm, A4[1]-29*mm, id='normal', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc = BaseDocTemplate(str(OUT), pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=13*mm, bottomMargin=16*mm, title='SUPADSP Research Paper', author='SUPADSP research team')
    doc.addPageTemplates([PageTemplate(id='paper', frames=frame, onPage=footer)])
    S=[]
    S += [P('SUPADSP: A Multi-Domain, Evidence-Grounded Decision-Support Platform for Urban Governance', 'PaperTitle'), P('Research manuscript | Version 1.0 | October 2026', 'Authors')]
    S += [P('<b>Abstract.</b> We present SUPADSP, a multi-domain platform for urban decision support that coordinates pollution, weather, energy, traffic, and simulation services through a supervisor gateway and a three-stage planner with machine-readable contracts, evidence evaluation, and response-scope enforcement. The pollution component includes a CPCB AQI engine and locally trained spatial-temporal forecasting candidates evaluated with seasonal rolling-origin validation. The deployed TemporalGRU with k-nearest-neighbor spatial covariates achieves a held-out AQI MAE of 11.38, compared with 12.21 for persistence, while directional accuracy remains below chance at all seven forecast horizons. Chronos-2 achieves the best cross-validation MAE (8.87) but degrades to 12.22 on the held-out regime, demonstrating a model-selection risk under seasonal shift. The paper also reports domain-appropriate results for weather ingestion, deterministic energy-profile fitting, SUMO traffic simulation, and evidence-grounded planning. The planner passes 123/123 grounding questions and 20/20 non-pollution regression questions. We explicitly distinguish trained models from provider ingestion, deterministic rules, and simulation, and document an energy benchmark leakage issue and a silent deployment-label failure.', 'Abstract')]
    S += [P('<b>Keywords:</b> smart city; urban computing; air-quality forecasting; multi-agent systems; grounded planning; SUMO simulation; model governance.', 'Smallx')]
    S += [P('1. Introduction', 'H1x'), P('Urban governance requires joint reasoning over heterogeneous signals: air quality, meteorology, traffic, electrical demand, and intervention scenarios. Conventional dashboards expose these streams independently, while natural-language systems can produce unsupported quantitative claims. SUPADSP addresses this gap with a supervisor gateway, specialist domain services, a structured planning loop, and verification safeguards.'), P('The contribution of this work is empirical and engineering-oriented rather than a claim of a new universal learning algorithm. First, we evaluate temporal, distance-based spatial, graph-based spatial, and pretrained time-series forecasting alternatives under seasonal regime shift. Second, we integrate domain services into a common evidence-grounded planning workflow. Third, we report traffic, energy, weather, and planning outcomes using metrics appropriate to each component. Finally, we document negative results and implementation boundaries so that the platform is not mischaracterized as a collection of fully trained models.')]
    S += fig('fig1_system_architecture.png', 175*mm, 'Figure 1. Reconstructed SUPADSP architecture. Solid arrows represent service and dispatch flow; dashed arrows represent evidence or reference data. The domains intentionally use different computational paradigms.')
    S += [P('2. System and Methods', 'H1x'), P('2.1 Architecture and domains', 'H2x'), P('The system contains a React/Vite decision cockpit, a FastAPI supervisor gateway, specialist services for pollution, weather, energy, traffic, and simulation, and a planner that performs intent gating, specialist dispatch, evidence sufficiency evaluation, synthesis, and response verification. The pollution forecasting candidates are locally trained on historical station archives. Chronos-2 is used as a pretrained foundation model. Weather is an external forecast-ingestion service with a deterministic fallback. Energy is a hybrid diurnal and physical-rule calculator, while traffic and simulation use SUMO and rule-based scenario logic.'), P('2.2 Air-quality forecasting', 'H2x'), P('The pollution service ingests seven criteria pollutants and computes CPCB sub-indices by breakpoint interpolation. The overall AQI is the maximum valid sub-index, subject to minimum-validity rules requiring at least three pollutants including a particulate pollutant. Forecast candidates use 14 days of context and a seven-day horizon over 13 monitoring stations. The locally trained GRU has two recurrent layers, hidden dimension 64, dropout 0.15, and temporal, pollutant, meteorological, and spatial covariates. The spatial ablation compares k-nearest-neighbor covariates with a Gaussian-distance graph-attention model and a temporal-only GRU.'), P('2.3 Seasonal evaluation', 'H2x'), P('We use three seasonal rolling-origin validation folds: monsoon washout, winter inversion peak, and summer transition. The final test window is a held-out winter period. Metrics include MAE, RMSE, coefficient of determination, AQI-category accuracy, directional accuracy, and validation-to-test degradation. The random seed is 42 and the model-selection discussion emphasizes robustness, not only the lowest validation mean.')]
    S += fig('fig2_forecasting_evaluation.png', 175*mm, 'Figure 2. Reconstructed results figure using verified metrics: model comparison, seven-day horizon behavior, domain-specific headline values, and evaluation coverage.')
    S += [P('2.4 Multi-domain services', 'H2x'), P('The weather component exposes provider-derived current conditions and forecast fields and returns a bounded deterministic fallback when external retrieval is unavailable. The energy component blends an empirical hourly profile with a Gaussian diurnal curve and applies temperature, EV, traffic-occupancy, and solar rules. Traffic and simulation use microscopic vehicle behavior and scenario perturbations. These services are not described as supervised models because the repository does not contain local training procedures or observational ground truth for them.'), P('2.5 Grounded planning', 'H2x'), P('The planner first gates the user intent and selects specialist capabilities from machine-readable contracts. It then dispatches requests, checks evidence sufficiency, optionally requests additional evidence, synthesizes a response, and applies numeric and scope verification. A rule-based fallback is evaluated separately from the language-model path.')]
    S += fig('fig3_grounded_planner_workflow.png', 175*mm, 'Figure 3. Evidence-grounded planner workflow. The pipeline supports bounded failure behavior and is evaluated as decision support, not as a replacement for expert or statutory approval.')
    S += [P('3. Results', 'H1x'), P('3.1 Forecasting results', 'H2x')]
    S += [table([
        ['Model','CV MAE','Test MAE','Test RMSE','Category accuracy'],
        ['TemporalGRU + kNN covariates','10.79','11.38','14.18','63.95%'],['Temporal-only GRU','10.98','11.76','14.08','64.29%'],['Persistence','9.74','12.21','15.93','59.47%'],['Chronos-2 + covariates','8.87','12.22','15.60','64.12%'],['Weighted GAT + GRU','11.79','13.32','15.81','65.12%'],['Seasonal naive','12.07','13.89','17.91','61.46%']], [43*mm,25*mm,25*mm,25*mm,31*mm]), P('Table 1. Cross-validation and held-out forecasting results.', 'Captionx')]
    S += [P('The kNN-covariate GRU is the strongest held-out model, but its advantage over persistence is modest: 0.83 AQI points. The GAT model underperforms both the simpler kNN model and the temporal-only GRU. Chronos-2 wins validation but suffers a 3.35-point validation-to-test increase, whereas the deployed kNN-GRU increases by 0.59. These results support robustness-aware model selection under regime shift rather than selection by a single validation score.'), P('Across D1-D7, the deployed model obtains MAEs of 8.76, 10.40, 11.49, 11.94, 12.00, 12.44, and 12.63. Directional accuracy is 40.0%, 36.5%, 23.5%, 36.5%, 36.5%, 45.9%, and 42.4%, respectively. Thus the model captures level information better than direction and should not be marketed as a reliable trend-direction predictor.')]
    S += [P('3.2 Domain-wide results', 'H2x')]
    S += [table([
        ['Domain','Computational status','Verified result'],
        ['Pollution','Locally trained GRU/GAT candidates plus CPCB engine','AQI MAE 11.38; RMSE 14.18; 4/12 exact CPCB matches; 7/12 within +/-2'],
        ['Weather','Provider ingestion with deterministic fallback; no local ML training','Integration and contract checks; no independent forecast MAE claimed'],
        ['Energy','Deterministic hybrid diurnal/physics model','MAPE 17.32%; MAE 0.1988 kW; RMSE 0.2488 kW; R2 0.8443; 100% top-eight profile overlap'],
        ['Traffic/simulation','SUMO microscopic simulation and rule-based demand','2,342 vehicles; 23.67 km/h mean speed; 87.64 s mean delay; 3,051.82 m maximum queue; 106 adaptations'],
        ['Planning','Contracted planner with verification and fallback','123/123 grounding; 20/20 regression; 60/60 fallback; 15/15 LLM-on advice'],
    ], [28*mm,65*mm,81*mm]), P('Table 2. Domain-specific outcomes. Values are not directly rank-comparable because each domain has a different target and measurement scale.', 'Captionx')]
    S += [P('3.3 AQI verification', 'H2x'), P('The CPCB engine was cross-checked against 12 usable station bulletin values. Four values matched exactly, seven were within +/-2 AQI points, and the prominent pollutant matched in all 12 cases. Remaining differences are consistent with the implementation using calendar-day arithmetic means while official bulletins use a retrospective rolling window.'), P('3.4 Planner verification', 'H2x'), P('The 123-question golden set covers station queries, observed status, forecasts, methodology, data quality, model limits, unavailable information, and adversarial questions. All 123 passed grounding checks without fabricated numbers. The non-pollution regression set passed 20/20. Advice evaluation passed 15/15 through the language-model path and 60/60 through the forced rule fallback.')]
    S += [P('4. Deployment-governance case study', 'H1x'), P('During automated model selection, a non-PyTorch candidate was silently saved under the label of another model because a default serialization branch assumed all candidates were PyTorch modules. The correction raises an error for unsupported model types, requires explicit deployment approval, stages candidate artifacts, and records the model class and deployment decision. This case demonstrates why model identity and artifact validation are part of scientific reproducibility, not merely operations tooling.')]
    S += [P('5. Discussion and limitations', 'H1x'), P('The platform demonstrates how heterogeneous urban services can be combined without pretending that every output has the same epistemic status. The strongest quantitative evidence is in pollution forecasting and planner contract evaluation. Weather output inherits the upstream provider and has no independent local forecast benchmark. Energy results are profile fitting on a single-household dataset, not grid forecasting; the empirical hourly profile is computed before the chronological split, creating leakage. Traffic values are SUMO scenario outputs rather than field validation. The test set contains 86 rolling windows, and test exposure occurred during development, so confidence intervals and external validation are needed before operational claims.'), P('The study is also limited by a single geographic case study, sparse station coverage, below-chance directional accuracy, incomplete pollutant coverage relative to all CPCB pollutants, and uncalibrated cross-domain coefficients. These limitations do not invalidate the platform demonstration, but they constrain generalization and motivate future work with reanalysis boundary-layer variables, independent cities, SCADA energy data, field traffic observations, leakage-free repeated experiments, and independent red-team evaluation.')]
    S += [P('6. Conclusion', 'H1x'), P('SUPADSP is a multi-domain decision-support platform that combines a trained pollution-forecasting component, provider-based weather ingestion, deterministic energy estimation, SUMO traffic simulation, and a grounded planning workflow. The empirical findings are mixed but informative: the kNN spatial-covariate GRU is the best held-out AQI model among the evaluated candidates, complex graph and foundation-model approaches do not automatically generalize, and the planner achieves strong contract-level grounding on the current evaluation sets. The principal practical lesson is that transparent boundaries, domain-specific metrics, and explicit failure reporting are necessary when integrating predictive and non-predictive components into an urban governance system.')]
    S += [P('Reproducibility', 'H1x'), P('The source manuscript, verified metrics, figure generator, reconstructed figures, and this PDF are stored in the project paper directory. The main evaluation commands are <font name="DejaVu-Bold">python scripts/evaluate_energy_model.py</font>, <font name="DejaVu-Bold">python paper/build_figures.py</font>, and the project pytest suites. The current environment does not contain a LaTeX compiler or Eclipse SUMO executable; therefore the supplied PDF is generated directly with ReportLab and the SUMO integration tests remain environment-blocked.')]
    S += [P('Selected references', 'H1x'), P('The manuscript uses the repository bibliography for CPCB AQI methodology, GRU and GAT architectures, air-quality forecasting, SUMO, grounded language-model agents, time-series foundation models, and machine-learning technical debt. See <font name="DejaVu-Bold">paper/references.bib</font> for the complete citation records.', 'Bodyx')]
    doc.build(S)
    print(f'Wrote {OUT}')


if __name__ == '__main__': build()
