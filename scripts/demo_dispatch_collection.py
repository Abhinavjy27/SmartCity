import json
import os
import sys

# Ensure repository root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.supervisor.main import app


def run_demonstration():
    client = TestClient(app)

    print("================================================================================")
    print("STEP 1: SUBMITTING PLANNER EXECUTION REQUEST WITH TRAFFIC & WEATHER OBJECTIVE")
    print("================================================================================")

    payload = {
        "request_id": "REQ-002",
        "objective": "Find the risk of heavy traffic due to rainfall in Narayanguda",
        "location": "Narayanguda, Hyderabad",
        "constraints": [],
    }
    print("Input Payload:")
    print(json.dumps(payload, indent=2))

    response = client.post("/agents/planner/execute", json=payload)
    print(f"\nResponse Status Code: {response.status_code}")
    execute_response = response.json()
    print("\nExecute Response Payload:")
    print(json.dumps(execute_response, indent=2))

    print("\n================================================================================")
    print("STEP 2: VERIFYING PLANNER AUTOMATIC CAPABILITY DETERMINATION & DISPATCH")
    print("================================================================================")
    selected_caps = execute_response["selected_capabilities"]
    dispatched_agents = execute_response["dispatched_agents"]
    print(f"Planner Selected Capabilities: {selected_caps}")
    print(f"Planner Dispatched Agents: {dispatched_agents}")

    # Check selective dispatch assertions
    assert "traffic" in selected_caps, "traffic should be selected"
    assert "weather" in selected_caps, "weather should be selected"
    assert "energy" not in selected_caps, "energy should NOT be selected"
    assert "pollution" not in selected_caps, "pollution should NOT be selected"

    assert "traffic_agent" in dispatched_agents, "traffic_agent should be dispatched"
    assert "weather_agent" in dispatched_agents, "weather_agent should be dispatched"

    print("Planner capability selection & dispatch verified: Only Traffic and Weather agents were dispatched.")

    print("\n================================================================================")
    print("STEP 3: COLLECTED RESULTS INSPECTION")
    print("================================================================================")
    collected = execute_response["agent_results"]
    for agent_cap, result in collected.items():
        print(f"\n--- Result for capability '{agent_cap}' ---")
        print(json.dumps(result, indent=2))

    print("\n================================================================================")
    print("STEP 4: VERIFYING PLANNER REASONING & FINAL CONSOLIDATED RESPONSE")
    print("================================================================================")
    final_response = execute_response.get("final_response")
    assert final_response is not None, "final_response should be present"
    print(f"Final Decision: {final_response.get('decision')}")
    print(f"Recommendation: {final_response.get('recommendation')}")
    print(f"Summary: {final_response.get('summary')}")
    print(f"Confidence: {execute_response.get('confidence')}")

    print("\n================================================================================")
    print("DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("================================================================================")


if __name__ == "__main__":
    run_demonstration()
