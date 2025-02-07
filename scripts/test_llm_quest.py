"""
Test script to run LLM agent on Space Rangers quest
"""
import sys
from pathlib import Path
import subprocess
import json

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.llm_agent import QuestAgent
from src.qm import parse_qm, QMGame

def run_llm_quest(quest_path: str, agent_cls=QuestAgent):
    """Run quest with LLM agent"""
    # Initialize QM game and agent
    game = parse_qm(quest_path)
    agent = agent_cls()

    current_location = game.get_location(game.start_id)

    while True:
        # Format observation for LLM
        observation = (
            f"{current_location.text}\n\n"
            "Available actions:\n"
        )
        for i, choice in enumerate(current_location.choices, 1):
            observation += f"{i}. {choice.text}\n"

        # Get LLM decision
        action = agent(observation)

        try:
            # Convert LLM response to choice index
            choice_idx = int(action.strip()) - 1
            if 0 <= choice_idx < len(current_location.choices):
                # Get next location
                next_loc_id = current_location.choices[choice_idx].jumpId
                current_location = game.get_location(next_loc_id)
                print(f"\nChose action {choice_idx + 1}")
            else:
                print(f"\nInvalid choice {action}, try again")
                continue

        except ValueError:
            print(f"\nInvalid response from LLM: {action}")
            continue

        # Check for end conditions (no more choices)
        if not current_location.choices:
            print("\nQuest completed!")
            print(f"Final location: {current_location.text}")
            break

if __name__ == "__main__":
    # Use example quest
    quest_path = project_root / "quests" / "boat.qm"
    if not quest_path.exists():
        print(f"Quest file not found: {quest_path}")
        sys.exit(1)

    print(f"\nStarting quest: {quest_path.name}")
    run_llm_quest(str(quest_path))