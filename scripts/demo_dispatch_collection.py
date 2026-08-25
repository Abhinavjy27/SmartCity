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
    print("STEP 1: SUBMITTING ORCHESTRATION REQUEST WITH TRAFFIC & WEATHER")
    print("================================================================================")

    payload = {
        "request_id": "REQ-002",
        "workflow": "monitor-detect-understand",
        "steps": [],
        "priority": 3,
        "objective": "Find the risk of heavy traffic due to rainfall",
        "location": "Narayanguda",
        "domains": ["traffic", "weather"],
        "constraints": [],
    }
    print("Input Payload:")
    print(json.dumps(payload, indent=2))

    response = client.post("/agents/orchestrator/execute", json=payload)
    print(f"\nResponse Status Code: {response.status_code}")
    execute_response = response.json()
    print("\nExecute Response Payload:")
    print(json.dumps(execute_response, indent=2))

    task_id = execute_response["task_id"]

    print("\n================================================================================")
    print("STEP 2: VERIFYING SELECTIVE DISPATCH")
    print("================================================================================")
    assigned_caps = execute_response["assigned_capabilities"]
    dispatched_agents = execute_response["dispatched_agents"]
    print(f"Assigned Capabilities: {assigned_caps}")
    print(f"Dispatched Agents: {dispatched_agents}")

    # Check selective dispatch assertions
    assert "traffic" in assigned_caps, "traffic should be assigned"
    assert "weather" in assigned_caps, "weather should be assigned"
    assert "energy" not in assigned_caps, "energy should NOT be assigned"
    assert "pollution" not in assigned_caps, "pollution should NOT be assigned"
    assert "simulation" not in assigned_caps, "simulation should NOT be assigned"

    assert "traffic_agent" in dispatched_agents, "traffic_agent should be dispatched"
    assert "weather_agent" in dispatched_agents, "weather_agent should be dispatched"
    assert "energy_agent" not in dispatched_agents, "energy_agent should NOT be dispatched"
    assert "pollution_agent" not in dispatched_agents, "pollution_agent should NOT be dispatched"
    assert "simulation_agent" not in dispatched_agents, "simulation_agent should NOT be dispatched"

    print("Selective dispatch verified: Only Traffic and Weather agents were dispatched.")

    print("\n================================================================================")
    print("STEP 3: COLLECTED RESULTS INSPECTION")
    print("================================================================================")
    collected = execute_response["collected_results"]
    for agent_cap, result in collected.items():
        print(f"\n--- Result for capability '{agent_cap}' ---")
        print(json.dumps(result, indent=2))

    print("\n================================================================================")
    print("STEP 4: VERIFYING PLANNER FEEDBACK")
    print("================================================================================")
    planner_feedback = execute_response.get("planner_feedback")
    assert planner_feedback is not None, "planner_feedback should be present"
    print(f"Feedback Status: {planner_feedback.get('status')}")
    print(f"Feedback Decision: {planner_feedback.get('decision')}")
    print(f"Synthesized Insights: {json.dumps(planner_feedback.get('insights'), indent=2)}")
    print(f"Planner Next Steps: {planner_feedback.get('next_steps')}")

    # Verify Planner received the exact mock results
    assert planner_feedback["received_results"] == collected, "Planner must receive exact collected results"
    print("Planner Feedback verified: Planner received exact collected results and produced next decision.")

    print("\n================================================================================")
    print("STEP 5: RETRIEVING FULL ORCHESTRATOR TASK STATE")
    print("================================================================================")
    task_response = client.get(f"/agents/orchestrator/tasks/{task_id}")
    print(f"Task Status Code: {task_response.status_code}")
    task_detail = task_response.json()
    print("\nFinal Orchestrator Task State:")
    print(json.dumps(task_detail, indent=2))

    print("\n================================================================================")
    print("DEMONSTRATION COMPLETED SUCCESSFULLY")
    print("================================================================================")


if __name__ == "__main__":
    run_demonstration()
