"""Run single quest with LLM agent"""
import argparse
from llm_quest_benchmark.runner import run_quest
from llm_quest_benchmark import constants

def main():
    parser = argparse.ArgumentParser(description="Run LLM agent on Space Rangers quest")
    parser.add_argument("--quest", default=constants.DEFAULT_QUEST)
    parser.add_argument("--log-level", choices=["debug", "info", "warning"], default="info")
    parser.add_argument("--output")
    args = parser.parse_args()
    return run_quest(args.quest, args.log_level, args.output)

if __name__ == "__main__":
    main()