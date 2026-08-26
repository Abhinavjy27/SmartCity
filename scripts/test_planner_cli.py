#!/usr/bin/env python3
"""
Interactive CLI testing script for the Planner Agent.
Allows testing queries in real-time against the live LLM.
"""

import json
import sys
import os

# Ensure repository root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.planner_agent.planner import PlannerAgent


def main():
    print("=" * 80)
    print("🧠 SUPADSP — Planner Agent Interactive Terminal")
    print("Type any query to test relevance, gatekeeping, and plan generation.")
    print("Type 'exit' or 'quit' to close.")
    print("=" * 80)

    try:
        agent = PlannerAgent()
    except Exception as exc:
        print(f"❌ Error initializing Planner Agent: {exc}")
        return

    while True:
        try:
            query = input("\n📝 Enter Query: ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            print("\n⏳ Processing query with Planner Agent...")
            result = agent.plan(query)

            print("\n📋 Planner Agent Output:")
            print(json.dumps(result.model_dump(), indent=2))

            if result.relevant:
                print(f"\n✅ RELEVANT: Plan generated with {len(result.plan)} steps.")
            else:
                print(f"\n🚫 REJECTED: {result.response}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as exc:
            print(f"\n❌ Error processing query: {exc}")


if __name__ == "__main__":
    main()
