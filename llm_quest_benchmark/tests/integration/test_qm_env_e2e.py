"""End-to-end tests for QM environment and agents."""
import pytest
import logging
from io import StringIO

from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.agents.simple_agent import SimpleQuestAgent
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.mark.integration
def test_qm_env_with_llm():
    """Test end-to-end interaction with QM environment using LLM agent."""
    # Setup logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Initialize environment and agent
    env = QMPlayerEnv(str(DEFAULT_QUEST), debug=True)
    agent = SimpleQuestAgent(debug=True, model_name="gpt-4o")

    try:
        # Reset environment
        observation = env.reset()
        assert observation is not None
        assert isinstance(observation, str)
        assert len(env.state['choices']) > 0

        # Take a step
        action = agent.get_action(observation, env.state['choices'])
        assert isinstance(action, str)
        assert action.isdigit()
        choice_num = int(action)
        assert 1 <= choice_num <= len(env.state['choices'])

        # Step environment
        next_observation, reward, done, info = env.step(action)
        assert isinstance(next_observation, str)
        assert isinstance(reward, (int, float))
        assert isinstance(done, bool)
        assert isinstance(info, dict)

    finally:
        # Clean up
        env.close()


@pytest.mark.integration
def test_qm_env_with_human():
    """Test end-to-end interaction with QM environment using human player."""
    # Setup mock input/output streams
    input_stream = StringIO("1\nq\n")  # First choice then quit
    output_stream = StringIO()

    # Initialize environment and player
    env = QMPlayerEnv(str(DEFAULT_QUEST), debug=True)
    player = HumanPlayer(debug=True, input_stream=input_stream, output_stream=output_stream)

    try:
        # Reset environment
        observation = env.reset()
        assert observation is not None
        assert isinstance(observation, str)
        assert len(env.state['choices']) > 0

        # Take a step (will use mocked input)
        action = player.get_action(observation, env.state['choices'])
        assert isinstance(action, str)
        assert action.isdigit()
        choice_num = int(action)
        assert 1 <= choice_num <= len(env.state['choices'])

        # Step environment
        next_observation, reward, done, info = env.step(action)
        assert isinstance(next_observation, str)
        assert isinstance(reward, (int, float))
        assert isinstance(done, bool)
        assert isinstance(info, dict)

        # Verify output
        output = output_stream.getvalue()
        assert "Quest Started" in output
        assert "Enter choice number" in output

    except KeyboardInterrupt:
        # Expected when human player quits
        pass
    finally:
        # Clean up
        env.close()