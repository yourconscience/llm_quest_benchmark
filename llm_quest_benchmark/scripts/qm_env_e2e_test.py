"""
Example to test the QMPlayer environment integration with TextArena.
This script registers the QMPlayer environment, creates a simple dummy agent,
and runs a game loop.
"""

from pathlib import Path
import textarena as ta
from textarena.envs.registration import register as ta_register
from llm_quest_benchmark.constants import QUESTS_DIR  # Use project constants

# Add src to Python path
import sys
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Register our custom QMPlayer environment
ta_register(
    id="QMPlayer-v0",
    entry_point="llm_quest_benchmark.environments.qm_env:QMPlayerEnv",
    qm_file=str(QUESTS_DIR / "boat.qm"),  # Use QUESTS_DIR constant
    max_steps=100
)

class DummyAgent:
    """Simple agent that always selects the first option"""
    def __call__(self, observation: str) -> str:
        print("\n--- Agent Observation ---")
        print(observation)
        return "1"  # Always choose first option

def main():
    # Create and wrap the environment
    env = ta.make("QMPlayer-v0")
    env = ta.wrappers.LLMObservationWrapper(env)
    env = ta.wrappers.SimpleRenderWrapper(env, player_names={0: "DummyAgent"})

    # Run test episode
    print("\nStarting test episode...")
    observations = env.reset()
    done = False
    agent = DummyAgent()

    try:
        while not done:
            player_id, obs = env.get_observation()
            action = agent(obs)
            print(f"\nAgent action: {action}")
            observations, rewards, done, info = env.step(action)
            env.render()
            if done:
                print(f"\nGame over! Final rewards: {rewards}")
                break
    except Exception as e:
        print(f"Error during episode: {e}")
        raise  # Re-raise to see full traceback during testing
    finally:
        env.close()

if __name__ == "__main__":
    main()