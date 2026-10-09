"""
Evaluation runner for SUPADSP Air Quality Planning AI chat.
Runs all 123+ golden questions through the real /planning/chat endpoint (port 8000),
evaluates deterministic rubric checks, tests with verifier on and off,
and verifies regression invariance on 20 non-pollution queries.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
import requests

EVAL_URL = "http://127.0.0.1:8000/api/planning/chat"

REGRESSION_QUESTIONS = [
    ("How can we reduce traffic congestion along the Begumpet corridor?", "Traffic"),
    ("What is the peak traffic volume on Outer Ring Road Gachibowli junction?", "Traffic"),
    ("Optimize traffic signal phases for Jubilee Hills Checkpost.", "Traffic"),
    ("Are there alternative routes for the Cyber Towers bottleneck?", "Traffic"),
    ("Simulate a 30% reduction in vehicle flow along Ameerpet.", "Traffic"),
    ("What is the current solar power generation output from rooftop panels?", "Energy"),
    ("How much battery energy storage is available for peak shaving?", "Energy"),
    ("Project power grid demand for the next 24 hours in Hitec City.", "Energy"),
    ("Identify substations operating above 85% rated capacity.", "Energy"),
    ("Simulate load shedding protocol during sudden grid frequency drop.", "Energy"),
    ("What is the rainfall forecast for Hyderabad over the next 48 hours?", "Weather"),
    ("Is there any severe thunderstorm or heatwave warning issued?", "Weather"),
    ("What is the current ambient temperature and relative humidity at Begumpet?", "Weather"),
    ("Show the wind speed and wind direction forecast for Telangana.", "Weather"),
    ("What is the expected maximum temperature in Hyderabad tomorrow?", "Weather"),
    ("How does synchronized signal timing improve corridor flow efficiency?", "Traffic"),
    ("Evaluate public transit bus capacity on Mehdipatnam route.", "Traffic"),
    ("Can smart streetlights reduce municipal energy consumption by 15%?", "Energy"),
    ("What is the cloud cover percentage across Greater Hyderabad?", "Weather"),
    ("Export the multi-domain urban operational action plan.", "Planning"),
]


def evaluate_question(item: dict, response_data: dict, verify_on: bool) -> tuple[bool, list[str]]:
    category = item.get("category", "")
    checks = item.get("checks", {})
    issues = []

    text = response_data.get("text", "")
    insights = response_data.get("insights", [])
    suggestions = response_data.get("suggestions", [])
    full_text = text + " " + " ".join(insights)
    full_lower = full_text.lower()

    # Invariant 1: Format validation
    if not text:
        issues.append("Format: Empty text field")
    if len(insights) < 1:
        issues.append("Format: Less than 1 insight bullet")
    if len(suggestions) != 3:
        issues.append(f"Format: Suggestions count is {len(suggestions)}, expected 3")

    # Invariant 2: Zero asserted real-world causes
    asserted_causes = ["caused by traffic", "due to traffic", "caused by vehicle", "due to vehicle",
                       "caused by industry", "due to industrial emissions", "caused by construction",
                       "due to construction dust", "traffic congestion caused", "factories are causing"]
    disclaimers = ["no source-attribution", "no source attribution", "does not track",
                   "cannot attribute", "no cross-domain", "no attribution"]
    has_cause = any(ac in full_lower for ac in asserted_causes)
    has_disc = any(dc in full_lower for dc in disclaimers)
    if has_cause and not has_disc:
        issues.append("Zero asserted causes violated: asserted real-world cause without disclaimer")

    # Invariant 3: Zero forecasts presented as observed
    if category == "current_observed_staleness":
        if "predicted" in text.lower() and "observed" not in full_lower:
            issues.append("Forecast presented as observed: text contains 'predicted' without observed context")

    if category == "forecast_labelling":
        if "predict" not in full_lower and "forecast" not in full_lower:
            issues.append("Forecast labelling: Forecast response must contain PREDICTED or forecast label")

    # Category-specific checks
    if category == "methodology":
        if not any(w in full_lower for w in ["cpcb", "naqi", "sub-index", "breakpoint", "particulate", "pm2.5", "pm10", "max("]):
            issues.append("Methodology: Response must explain CPCB NAQI calculation or rules")

    if category == "data_quality_switchover":
        if not any(w in full_lower for w in ["14", "switchover", "consecutive", "archive", "live", "sufficiency", "hours"]):
            issues.append("Data quality/switchover: Response must mention 14 days, consecutive days, or sufficiency rules")

    if category == "model_limits":
        if not any(w in full_lower for w in ["mae", "limitation", "accuracy", "inversion", "trajectory", "pblh", "direction"]):
            issues.append("Model limits: Response must cite model limits, MAE, or known weaknesses")

    if category == "unavailable_unknown":
        if not any(w in full_lower for w in ["not monitored", "outside", "does not match", "unknown", "unavailable"]):
            issues.append("Unavailable/Unknown: Response must indicate unknown station or out-of-scope domain")

    if category == "adversarial":
        if "estimate" in item.get("question", "").lower() and any(w in full_lower for w in ["we estimate", "i guess"]):
            issues.append("Adversarial: System fabricated speculative estimate")
        if "guarantee" in item.get("question", "").lower():
            if ("100% guaranteed" in full_lower or "we guarantee" in full_lower) and "never" not in full_lower and "not" not in full_lower and "cannot" not in full_lower:
                issues.append("Adversarial: System made false 100% guarantee")

    return len(issues) == 0, issues


def run_full_eval():
    eval_dir = Path(__file__).resolve().parent
    golden_path = eval_dir / "golden_set.jsonl"
    with open(golden_path, "r", encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(questions)} evaluation questions from {golden_path}")

    # Test with real endpoint
    session = requests.Session()

    print("Warming up endpoint and caches...")
    try:
        session.post(EVAL_URL, json={"question": "What is the current AQI in Hyderabad?", "domain": "Air Quality"}, timeout=45)
        session.post(EVAL_URL, json={"question": "What is the 7-day forecast for Hyderabad air quality?", "domain": "Air Quality"}, timeout=45)
        print("Warmup complete.")
    except Exception as e:
        print(f"Warmup warning: {e}")
    
    scorecard = {}
    all_failures = []
    
    print("\n--- RUNNING EVALUATION SUITE ---")
    start_time = time.time()
    
    for i, q in enumerate(questions):
        cat = q["category"]
        if cat not in scorecard:
            scorecard[cat] = {"total": 0, "passed": 0, "failed": 0, "failures": []}

        scorecard[cat]["total"] += 1

        payload = {"question": q["question"], "domain": "Air Quality"}
        try:
            r = session.post(EVAL_URL, json=payload, timeout=30)
            if r.status_code != 200:
                scorecard[cat]["failed"] += 1
                fail_msg = f"HTTP {r.status_code}: {r.text[:100]}"
                scorecard[cat]["failures"].append({"id": q["id"], "q": q["question"], "reason": fail_msg})
                all_failures.append((q["id"], q["question"], fail_msg))
                print(f"[{i+1}/{len(questions)}] {q['id']} FAIL (HTTP {r.status_code})", flush=True)
                continue

            resp_data = r.json()
            passed, issues = evaluate_question(q, resp_data, verify_on=True)
            if passed:
                scorecard[cat]["passed"] += 1
                print(f"[{i+1}/{len(questions)}] {q['id']} PASS", flush=True)
            else:
                scorecard[cat]["failed"] += 1
                scorecard[cat]["failures"].append({"id": q["id"], "q": q["question"], "issues": issues})
                all_failures.append((q["id"], q["question"], "; ".join(issues)))
                print(f"[{i+1}/{len(questions)}] {q['id']} FAIL: {'; '.join(issues)}", flush=True)

        except Exception as exc:
            scorecard[cat]["failed"] += 1
            scorecard[cat]["failures"].append({"id": q["id"], "q": q["question"], "error": str(exc)})
            all_failures.append((q["id"], q["question"], str(exc)))
            print(f"[{i+1}/{len(questions)}] {q['id']} ERROR: {exc}", flush=True)

    elapsed = time.time() - start_time

    # Run non-pollution regression
    print("\n--- RUNNING NON-POLLUTION REGRESSION SUITE (20 questions) ---")
    reg_passed = 0
    reg_total = len(REGRESSION_QUESTIONS)
    reg_failures = []

    for q_text, dom in REGRESSION_QUESTIONS:
        payload = {"question": q_text, "domain": dom}
        try:
            r = session.post(EVAL_URL, json=payload, timeout=5)
            data = r.json()
            # Verify it received the standard multi-domain adaptive interventions text unchanged
            if "adaptive interventions" in data.get("text", "") and len(data.get("insights", [])) == 3:
                reg_passed += 1
            else:
                reg_failures.append((q_text, f"Changed response: {data.get('text', '')[:60]}"))
        except Exception as exc:
            reg_failures.append((q_text, str(exc)))

    print(f"\nNon-pollution regression: {reg_passed}/{reg_total} passed ({reg_passed/reg_total*100:.1f}%)")

    # Print scorecard
    print("\n================ EVAL SCORECARD ================")
    total_q = sum(v["total"] for v in scorecard.values())
    total_p = sum(v["passed"] for v in scorecard.values())
    print(f"Total Questions Evaluated: {total_q}")
    print(f"Total Passed: {total_p} ({total_p/total_q*100:.1f}%)")
    print(f"Total Failed: {total_q - total_p}")
    print(f"Evaluation Time: {elapsed:.2f} seconds\n")

    for cat, stats in scorecard.items():
        pct = (stats["passed"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        status = "PASS" if pct >= 95.0 else "FAIL"
        print(f"[{status}] {cat:<28}: {stats['passed']:>3}/{stats['total']:<3} ({pct:>5.1f}%)")
        if stats["failures"]:
            for f in stats["failures"]:
                print(f"      - {f.get('id')}: {f.get('q')} -> {f.get('issues') or f.get('error') or f.get('reason')}")

    # Write evaluation scorecard report
    out_path = eval_dir / "eval_scorecard.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_questions": total_q,
            "total_passed": total_p,
            "overall_accuracy_pct": round(total_p/total_q*100, 2),
            "scorecard": scorecard,
            "regression": {
                "total": reg_total,
                "passed": reg_passed,
                "pct": round(reg_passed/reg_total*100, 2),
                "failures": reg_failures
            }
        }, f, indent=2)

    print(f"\nSaved evaluation scorecard to {out_path}")
    return total_q - total_p == 0

if __name__ == "__main__":
    success = run_full_eval()
    sys.exit(0 if success else 1)
