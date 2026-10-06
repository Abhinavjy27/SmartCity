"""
Fetch verbatim planning chat responses for the 5 mandated questions in Section 3 of final report:
1. what's the weather in Hyderabad now
2. will it rain tomorrow
3. why is AQI high in Nacharam
4. is the weather making AQI worse
5. how to reduce traffic along Begumpet
"""

import json
import urllib.request

QUESTIONS = [
    ("weather", "what's the weather in Hyderabad now"),
    ("weather", "will it rain tomorrow"),
    ("pollution", "why is AQI high in Nacharam"),
    ("combined", "is the weather making AQI worse"),
    ("traffic", "how to reduce traffic along Begumpet"),
]

def main():
    url = "http://127.0.0.1:8000/api/planning/chat"
    results = {}
    for domain, q in QUESTIONS:
        payload = json.dumps({"question": q, "domain": domain}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results[q] = data
            print(f"=== Q: {q} ===")
            print(json.dumps(data, indent=2))
            print()

    with open("eval/verbatim_section3_answers.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
