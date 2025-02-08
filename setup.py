from setuptools import setup, find_packages

def get_requirements():
    with open("requirements.txt") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="llm_quest_benchmark",
    version="0.1.0",
    packages=find_packages(),
    package_data={
        "llm_quest_benchmark": [
            "prompt_templates/*.jinja",
            "parsers/qm/*.ts"
        ]
    },
    install_requires=get_requirements(),
    entry_points={
        "console_scripts": [
            "llm-quest=llm_quest_benchmark.scripts.run_quest:main",
            "llm-analyze=llm_quest_benchmark.scripts.analyze_metrics:main",
            "qm-player=llm_quest_benchmark.scripts.qm_player:main"
        ]
    }
)