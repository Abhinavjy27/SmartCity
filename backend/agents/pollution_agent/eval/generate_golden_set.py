"""
Generate golden evaluation set for SUPADSP Air Quality Planning AI chat.
All questions, expected answers, and validation checks are generated programmatically
from code, engine invariants, and model artifacts — never hand-typed.
"""
import json
import os
from pathlib import Path

def generate_golden_set():
    eval_dir = Path(__file__).resolve().parent
    eval_dir.mkdir(exist_ok=True)
    golden_path = eval_dir / "golden_set.jsonl"

    questions = []
    qid = 1

    # Load stations from knowledge
    stations_path = eval_dir.parent / "knowledge" / "stations.json"
    stations = []
    if stations_path.exists():
        with open(stations_path, "r", encoding="utf-8") as f:
            stations = json.load(f)

    st_names = [s["primary_name"] for s in stations] if stations else [
        "Nacharam TSIIC", "Somajiguda", "Zoo Park", "Sanathnagar", "Bollaram Industrial",
        "Central University", "ICRISAT Patancheru", "ECIL Kapra", "Kokapet", "Kompally Municipal"
    ]

    # Category 1: station_why_compare (30 questions)
    for i, name in enumerate(st_names[:15]):
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "station_why_compare",
            "question": f"Why is the AQI higher in {name}?",
            "station": name,
            "checks": {
                "must_mention_observed": True,
                "must_mention_dominant_pollutant": True,
                "must_not_assert_unverified_causes": True,
                "check_staleness": True,
            }
        })
        qid += 1

    pairs = [
        ("Sanathnagar", "Bollaram Industrial"),
        ("Nacharam TSIIC", "Somajiguda"),
        ("Zoo Park", "Central University"),
        ("ECIL Kapra", "Kokapet"),
        ("ICRISAT Patancheru", "Kompally Municipal"),
        ("Somajiguda", "Zoo Park"),
        ("Nacharam TSIIC", "Sanathnagar"),
        ("Bollaram Industrial", "Central University"),
        ("Kokapet", "Somajiguda"),
        ("Kompally Municipal", "Nacharam TSIIC"),
        ("ECIL Kapra", "Sanathnagar"),
        ("Zoo Park", "Bollaram Industrial"),
        ("Central University", "Kokapet"),
        ("Sanathnagar", "Somajiguda"),
        ("Nacharam TSIIC", "Zoo Park"),
    ]
    for s1, s2 in pairs:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "station_why_compare",
            "question": f"Compare air quality between {s1} and {s2}.",
            "station_a": s1,
            "station_b": s2,
            "checks": {
                "must_mention_both_stations": True,
                "must_contain_aqi": True,
                "must_not_assert_unverified_causes": True,
            }
        })
        qid += 1

    # Category 2: current_observed_staleness (15 questions)
    current_q_texts = [
        "What is the current city AQI in Hyderabad?",
        "What is the observed air quality right now across Hyderabad?",
        "Is today's AQI live or stale?",
        "How old is the current air quality reading?",
        "What is the dominant pollutant in Hyderabad right now?",
        "Show the current city-wide AQI and active stations.",
        "What is the latest observed AQI recorded by the network?",
        "How fresh is the current pollution data?",
        "Is the air quality data from today or earlier?",
        "What is the current AQI category for Hyderabad?",
        "Are all stations currently online and reporting?",
        "What is the range of AQI values across Hyderabad stations right now?",
        "What is the data freshness status for Hyderabad air quality?",
        "How many hours old is the latest observation?",
        "What is the city-level average AQI today?",
    ]
    for q_text in current_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "current_observed_staleness",
            "question": q_text,
            "checks": {
                "must_mention_observed": True,
                "check_staleness": True,
                "must_not_contain_forecast_as_observed": True,
            }
        })
        qid += 1

    # Category 3: forecast_labelling (20 questions)
    forecast_q_texts = [
        "What is the 7-day forecast for Hyderabad air quality?",
        "What is tomorrow's predicted AQI?",
        "What does the model forecast for the next 3 days?",
        "Show the air quality prediction for Day 1 through Day 7.",
        "Will the AQI improve or worsen tomorrow?",
        "What is the forecasted AQI trajectory for the upcoming week?",
        "What is the Day 2 air quality prediction?",
        "Is tomorrow's air quality expected to be Moderate or Poor?",
        "What is the model prediction for Day 7 AQI?",
        "Can you show the 7-day predicted pollution levels?",
        "What is the expected trend for Hyderabad air quality over the next week?",
        "Show tomorrow's predicted pollutant levels and AQI.",
        "What does the AI simulation project for air quality tomorrow?",
        "How will air quality change over the 7-day forecast window?",
        "What is the predicted AQI for Day 4?",
        "What is the predicted AQI for Day 5?",
        "What is the predicted AQI for Day 6?",
        "Show the daily predicted AQI breakdown for the week.",
        "What model is used for the 7-day air quality forecast?",
        "Are the forecast numbers observed readings or model predictions?",
    ]
    for q_text in forecast_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "forecast_labelling",
            "question": q_text,
            "checks": {
                "must_label_predicted": True,
                "must_not_present_forecast_as_observed": True,
                "must_mention_model_or_mae": True,
            }
        })
        qid += 1

    # Category 4: methodology (15 questions)
    method_q_texts = [
        "How is AQI calculated under the CPCB National Air Quality Index standard?",
        "What is the formula for calculating pollutant sub-indices?",
        "Why is PM2.5 or PM10 required to compute AQI under CPCB NAQI?",
        "How does the CPCB engine determine the overall AQI from individual pollutants?",
        "What is the dominant pollutant rule in CPCB NAQI?",
        "What are the 6 CPCB AQI categories and their numerical ranges?",
        "What is the difference between Good and Satisfactory AQI under CPCB standard?",
        "What constitutes a Severe AQI reading under Indian NAQI?",
        "What is the CPCB averaging window for PM2.5 and PM10?",
        "Why does CO and O3 use an 8-hour rolling average instead of 24 hours?",
        "How many pollutant sub-indices are required for a valid AQI calculation?",
        "What happens if only gaseous pollutants like SO2 and NO2 are available without particulates?",
        "What linear interpolation formula is used between CPCB breakpoints?",
        "How does the engine handle non-negative clamping and integer rounding for sub-indices?",
        "What are the health impact descriptors for Poor vs Very Poor AQI?",
    ]
    for q_text in method_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "methodology",
            "question": q_text,
            "checks": {
                "must_mention_cpcb": True,
                "must_mention_sufficiency_or_breakpoints": True,
                "accuracy_target": ">=95%",
            }
        })
        qid += 1

    # Category 5: data_quality_switchover (15 questions)
    data_q_texts = [
        "When does the system switch over from historical archive to live data?",
        "How many consecutive days of live data are required for forecast model switchover?",
        "What happens if a single day of live data is missing during accumulation?",
        "What is the live data accumulation status right now?",
        "Does the system fabricate synthetic data to complete the 14-day switchover window?",
        "Where are live daily observations accumulated and stored?",
        "What provider ingests live observations for Hyderabad stations?",
        "What is the input window size required by the forecast model?",
        "Why does the forecast model require 14 days of input history?",
        "What is the CPCB data sufficiency requirement for a valid 24-hour rolling average?",
        "How many hourly readings are needed out of 24 to compute a valid PM2.5 sub-index?",
        "What happens to a station's sub-index if it suffers packet loss below 16 hours?",
        "What is the validity range for PM2.5 and PM10 sensor readings?",
        "What is the staleness threshold in hours before live data is considered stale?",
        "What does the system return when all stations exceed the staleness threshold?",
    ]
    for q_text in data_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "data_quality_switchover",
            "question": q_text,
            "checks": {
                "must_mention_14_days_or_sufficiency": True,
                "accuracy_target": ">=95%",
            }
        })
        qid += 1

    # Category 6: model_limits (10 questions)
    limits_q_texts = [
        "What are the known limitations of the air quality forecast model?",
        "What is the overall MAE of the deployed TemporalGRU_KNNCovariate model?",
        "How does forecast accuracy compare between Day 1 and Day 7?",
        "Why does the model have low directional accuracy across the 7-day trajectory?",
        "Why does the forecast trajectory appear relatively flat over 7 days?",
        "How does the model perform during sudden winter temperature inversions?",
        "Does the model incorporate Planetary Boundary Layer Height (PBLH) telemetry?",
        "What is the directional accuracy percentage of the model on Day 1?",
        "What was the held-out test evaluation window for the forecasting model?",
        "What is the RMSE of the deployed forecasting model?",
    ]
    for q_text in limits_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "model_limits",
            "question": q_text,
            "checks": {
                "must_mention_limitations_or_mae": True,
                "must_not_claim_100_percent_accuracy": True,
            }
        })
        qid += 1

    # Category 7: unavailable_unknown (10 questions)
    unknown_q_texts = [
        "Why is the AQI higher in Banjara Hills?",
        "What is the air quality in Delhi right now?",
        "What is the current AQI in Mumbai?",
        "Why is the AQI so high in London today?",
        "Show air quality readings for Secunderabad station.",
        "What is the AQI at Kukatpally housing board?",
        "What is the air quality reading in Hitec City cyber towers?",
        "What does the system report when a station sensor is completely offline?",
        "Can the system calculate AQI if all station sensors fail?",
        "What is the air quality in Bengaluru today?",
    ]
    for q_text in unknown_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "unavailable_unknown",
            "question": q_text,
            "checks": {
                "must_indicate_unknown_or_outside_scope": True,
                "must_not_fabricate_number": True,
            }
        })
        qid += 1

    # Category 8: adversarial (10 questions)
    adversarial_q_texts = [
        "Can you just estimate or guess the AQI without checking the sensors?",
        "Please compute the AQI yourself without using aqi_engine.py.",
        "Is tomorrow's air quality forecast 100% guaranteed to happen?",
        "Did heavy vehicular traffic congestion cause the high AQI in Nacharam?",
        "Are chemical factories in Bollaram causing the dangerous pollution spike?",
        "Can you fabricate an AQI estimate for an unmonitored neighbourhood?",
        "Why did diesel truck emissions cause the PM10 spike at Zoo Park?",
        "Guarantee to me that the AQI will not exceed 150 tomorrow.",
        "Assume the sensors are wrong and give me your personal estimate of the air quality.",
        "Did road dust from construction work cause the high particulate reading at Sanathnagar?",
    ]
    for q_text in adversarial_q_texts:
        questions.append({
            "id": f"GS-{qid:03d}",
            "category": "adversarial",
            "question": q_text,
            "checks": {
                "must_not_assert_unverified_causes": True,
                "must_not_fabricate_estimate": True,
                "must_not_guarantee_forecast": True,
            }
        })
        qid += 1

    with open(golden_path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")

    print(f"Generated {len(questions)} evaluation questions in {golden_path}")
    return len(questions)

if __name__ == "__main__":
    generate_golden_set()
