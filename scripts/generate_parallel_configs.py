"""Generate per-model benchmark configs for parallel execution."""

from pathlib import Path

import yaml

QUESTS = [
    "quests/Boat.qm",
    "quests/sr_2_1_2121_eng/Badday_eng.qm",
    "quests/sr_2_1_2121_eng/Banket_eng.qm",
    "quests/sr_2_1_2121_eng/Codebox_eng.qm",
    "quests/sr_2_1_2121_eng/Depth_eng.qm",
    "quests/sr_2_1_2121_eng/Driver_eng.qm",
    "quests/sr_2_1_2121_eng/Edelweiss_eng.qm",
    "quests/sr_2_1_2121_eng/Election_eng.qm",
    "quests/sr_2_1_2121_eng/Foncers_eng.qm",
    "quests/sr_2_1_2121_eng/Leonardo_eng.qm",
    "quests/sr_2_1_2121_eng/Ministry_eng.qm",
    "quests/sr_2_1_2121_eng/Pizza_eng.qm",
    "quests/sr_2_1_2121_eng/Prison_eng.qm",
    "quests/sr_2_1_2121_eng/Robots_eng.qm",
    "quests/sr_2_1_2121_eng/Ski_eng.qm",
]

MODELS = [
    ("google/gemini-3-flash-preview", "gemini3_flash"),
    ("openai/gpt-5.4-mini", "gpt54_mini"),
    ("deepseek/deepseek-v3.2", "deepseek_v3"),
    ("mistralai/mistral-medium-3.1", "mistral_medium"),
    ("anthropic/claude-haiku-4.5", "haiku45"),
    ("minimax/minimax-m2.5", "minimax_m25"),
]

TEMPLATES = ["stub", "reasoning"]
RUNS = 3
TEMPERATURE = 0.4
QUEST_TIMEOUT = 600

output_dir = Path("configs/benchmarks/phase1")
output_dir.mkdir(parents=True, exist_ok=True)

for model_id, short_name in MODELS:
    config = {
        "name": f"phase1_{short_name}",
        "quests": QUESTS,
        "agents": [
            {
                "model": f"openrouter:{model_id}",
                "template": template,
                "temperature": TEMPERATURE,
                "runs": RUNS,
            }
            for template in TEMPLATES
        ],
        "debug": False,
        "quest_timeout": QUEST_TIMEOUT,
        "max_workers": 1,
        "output_dir": "results/benchmarks",
    }
    path = output_dir / f"phase1_{short_name}.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"Generated: {path}")

print(
    f"\nGenerated {len(MODELS)} configs, {len(QUESTS)} quests x {len(TEMPLATES)} templates x {RUNS} runs = {len(QUESTS) * len(TEMPLATES) * RUNS} runs per model"
)
print(f"Total: {len(MODELS) * len(QUESTS) * len(TEMPLATES) * RUNS} runs")
print("\nTo run in parallel:")
for _, short_name in MODELS:
    print(f"  uv run llm-quest benchmark --config configs/benchmarks/phase1/phase1_{short_name}.yaml &")
