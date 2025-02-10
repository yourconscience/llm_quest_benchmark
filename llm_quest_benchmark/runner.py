"""
Main quest runner implementation.
Runs a quest using the QM environment, agent, and renderer.
Logs step-by-step metrics for tracing run evolution.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from llm_quest_benchmark.constants import DEFAULT_MODEL
from llm_quest_benchmark.agents.llm_agent import QuestAgent
from llm_quest_benchmark.environments.qm_env import QMPlayerEnv
from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer
from llm_quest_benchmark.metrics import MetricsLogger


def run_quest(
    quest: str,
    log_level: str = "info",
    output: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    metrics: bool = False,
) -> int:
    # Configure logging
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.info("Runner started!")

    # Initialize components
    env = QMPlayerEnv(quest)
    agent = QuestAgent(debug=(log_level == "debug"), model_name=model)
    logging.info(f"Using model: {model}")
    renderer = QuestRenderer(env)

    # Initialize our metrics logger
    metrics_logger = MetricsLogger(auto_save=metrics)
    if metrics:
        metrics_logger.set_quest_file(quest)
    step_count = 0

    # Reset environment and render initial state
    obs = env.reset()
    renderer.render()

    while True:
        step_count += 1

        # Assume obs[0] contains the state text (if obs is a list)
        current_state = obs[0] if isinstance(obs, list) and obs else {"text": ""}
        if isinstance(current_state, str):
            current_state = {"text": current_state}

        # Agent selects an action based on the current state text
        action = agent(current_state.get("text", ""))
        # Log the choice before stepping (choice not yet determined in non-interactive mode)
        metrics_logger.log_step(step_count, current_state, choice="", action=action, reward=0)

        # Execute the action in the environment
        obs, reward, done, info = env.step(action)
        renderer.render()

        # Log after the step (we record the reward from this step)
        new_state = obs[0] if isinstance(obs, list) and obs else {"text": ""}
        if isinstance(new_state, str):
            new_state = {"text": new_state}
        metrics_logger.log_step(step_count, new_state, choice=action, action=action, reward=reward[0])

        if done:
            if reward[0] > 0:
                print("\n🎉 Quest completed successfully!")
            else:
                print("\n💥 Quest failed!")
            break

    # Compile final metrics
    env_metrics = env.get_metrics()
    env_metrics.update({
        "quest_file": quest,
        "completion_time": datetime.now().isoformat(),
        "final_reward": reward[0],
    })

    # Save metrics if an output file is provided
    if output:
        metrics_logger.save_metrics(env_metrics, output)
        print(f"\nMetrics saved to: {output}")
    elif metrics:
        saved_path = metrics_logger.save()
        if saved_path:
            print(f"\nMetrics automatically saved to: {saved_path}")

    return 0 if reward[0] > 0 else 1
