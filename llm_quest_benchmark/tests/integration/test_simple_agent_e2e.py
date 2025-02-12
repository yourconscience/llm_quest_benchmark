"""End-to-end tests for simple agent"""
import logging
import pytest

from llm_quest_benchmark.agents.simple_agent import SimpleQuestAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.mark.integration
def test_simple_agent_boat_quest():
    """Test that simple agent can complete the boat quest"""
    # Enable debug logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

    # Create environment with debug enabled
    logger.info("Creating environment...")
    env = QMPlayerEnv(str(DEFAULT_QUEST), debug=True)

    # Create agent
    logger.info("Creating agent...")
    agent = SimpleQuestAgent(debug=True, model_name="gpt-4o")

    # Run episode
    logger.info("Starting episode...")
    observation = env.reset()
    done = False
    total_reward = 0
    step_count = 0
    max_steps = 50  # Prevent infinite loops during testing

    try:
        while not done and step_count < max_steps:
            step_count += 1
            logger.info(f"\n=== Step {step_count} ===")

            # Get agent's action
            action = agent(observation)
            logger.debug(f"Agent chose action: {action}")

            # Take step in environment
            observation, reward, done, info = env.step(action)
            total_reward += reward

            if 'error' in info:
                logger.warning(f"Error in step: {info['error']}")

        if step_count >= max_steps:
            logger.warning("Episode stopped due to max steps")
        else:
            logger.info(f"Episode finished with total reward: {total_reward}")

        assert total_reward > 0, "Quest should complete successfully"

    except Exception as e:
        logger.exception("Error during episode")
        raise