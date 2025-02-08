"""
Enhanced end-to-end quest runner with logging and metrics
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

def validate_project_structure():
    """Ensure script is run from project root with required directories"""
    required_dirs = [
        Path("src"),
        Path("quests"),
        Path("scripts")
    ]

    missing = [d for d in required_dirs if not d.exists()]
    if missing:
        print("ERROR: Please run from project root directory!")
        print("Missing directories:", [str(d) for d in missing])
        sys.exit(1)

def main():
    validate_project_structure()

    parser = argparse.ArgumentParser(description="Run LLM agent on Space Rangers quest")
    parser.add_argument("--quest", type=str, default="quests/boat.qm",
                      help="Path to QM quest file")
    parser.add_argument("--log-level", choices=["debug", "info", "warning"], default="info",
                      help="Logging verbosity level")
    parser.add_argument("--output", type=str,
                      help="Path to save metrics JSON file")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize components
    from llm_quest_benchmark.qm_adapter import QMPlayerEnv
    from llm_quest_benchmark.llm_agent import QuestAgent
    from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer

    env = QMPlayerEnv(args.quest)
    agent = QuestAgent(debug=(args.log_level == "debug"))
    renderer = QuestRenderer(env)

    # Run quest
    obs = env.reset()
    renderer.render()

    while True:
        action = agent(obs[0])  # Get action from agent
        obs, reward, done, info = env.step(action)
        renderer.render()

        if done:
            if reward[0] > 0:
                print("\n🎉 Quest completed successfully!")
            else:
                print("\n💥 Quest failed!")
            break

    # Save metrics
    metrics = env.get_metrics()
    metrics.update({
        'quest_file': args.quest,
        'completion_time': datetime.now().isoformat(),
        'final_reward': reward[0]
    })

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"\nMetrics saved to: {output_path}")

    return 0 if reward[0] > 0 else 1

if __name__ == "__main__":
    exit(main())