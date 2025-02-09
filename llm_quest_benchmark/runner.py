"""
Main quest runner implementation
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from llm_quest_benchmark.agents.llm_agent import QuestAgent
from llm_quest_benchmark.environments.qm_env import QMPlayerEnv
from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer


def run_quest(quest: str, log_level: str = "info", output: Optional[str] = None) -> int:

    # Configure logging
    logging.basicConfig(level=log_level.upper(),
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    logging.info("Runner started!")

    # Initialize components
    env = QMPlayerEnv(quest)
    agent = QuestAgent(debug=(log_level == "debug"))
    renderer = QuestRenderer(env)

    # Run quest
    obs = env.reset()
    renderer.render()

    while True:
        action = agent(obs[0])
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
        'quest_file': quest,
        'completion_time': datetime.now().isoformat(),
        'final_reward': reward[0]
    })

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"\nMetrics saved to: {output_path}")

    return 0 if reward[0] > 0 else 1
