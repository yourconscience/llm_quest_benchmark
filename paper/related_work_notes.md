# Related Work Notes

This file captures the web research used to frame the draft and the paper bibliography.

## Closest text-game and interactive benchmarks

- `TextQuests` - Long Phan, Mantas Mazeika, Andy Zou, Dan Hendrycks. "TextQuests: How Good are LLMs at Text-Based Video Games?" arXiv:2507.23701, 2025.
  Link: https://arxiv.org/abs/2507.23701
  Relevance: closest recent LLM benchmark on long-horizon interactive fiction. It uses Infocom parser games and explicitly forbids external tools, which contrasts with this repo's choice-based Space Rangers quests and explicit architecture comparison.

- `TextWorld` - Marc-Alexandre Cote et al. "TextWorld: A Learning Environment for Text-based Games." arXiv:1806.11532, 2018.
  Link: https://arxiv.org/abs/1806.11532
  Relevance: foundational text-game environment, but mostly procedural/RL-oriented rather than a benchmark of prompting and agent scaffolding on authored quests.

- `TextGames` - Frederikus Hudi et al. "TextGames: Learning to Self-Play Text-Based Puzzle Games via Language Model Reasoning." arXiv:2502.18431, 2025.
  Link: https://arxiv.org/abs/2502.18431
  Relevance: difficulty-tier framing and reasoning stress tests for puzzle-style text tasks.

- `Playing With AI` - Berry Gerrits. "Playing With AI: How Do State-Of-The-Art Large Language Models Perform in the 1977 Text-Based Adventure Game Zork?" arXiv:2602.15867, 2026.
  Link: https://arxiv.org/abs/2602.15867
  Relevance: recent evidence that modern chat models still struggle badly on classic text adventure tasks, even with stronger prompting.

- `lmgame-Bench` - Lanxiang Hu et al. "lmgame-Bench: How Good are LLMs at Playing Games?" arXiv:2505.15146, 2025.
  Link: https://arxiv.org/abs/2505.15146
  Relevance: broader game benchmark with a unified API and contamination-focused benchmark design.

## General LLM-agent benchmarking

- `AgentBench` - Xiao Liu et al. "AgentBench: Evaluating LLMs as Agents." arXiv:2308.03688, ICLR 2024.
  Link: https://arxiv.org/abs/2308.03688
  Relevance: general multi-environment agent benchmark. Useful contrast because it varies environments more than agent scaffolds.

- `AgentQuest` - Luca Gioacchini et al. "AgentQuest: A Modular Benchmark Framework to Measure Progress and Improve LLM Agents." NAACL 2024 demo / arXiv:2404.06411.
  Links: https://aclanthology.org/2024.naacl-demo.19/ and https://arxiv.org/abs/2404.06411
  Relevance: modular benchmark framing and progress-oriented metrics.

## Architecture references

- `Chain-of-Thought Prompting` - Jason Wei et al. "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS 2022.
- `ReAct` - Shunyu Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023 / arXiv:2210.03629.
- `Toolformer` - Timo Schick et al. "Toolformer: Language Models Can Teach Themselves to Use Tools." NeurIPS 2023 / arXiv:2302.04761.

These are cited to motivate the benchmark modes, not because the repo implements them exactly.

## Space Rangers-specific resources

- Space Rangers community quest archive:
  https://gitlab.com/spacerangers
  Relevance: upstream quest corpus used by the benchmark.

- `space-rangers-quest` TypeScript engine:
  https://github.com/roginvs/space-rangers-quest
  Relevance: quest interpreter used by the Python bridge in this repo.
