# Benchmark Landscape: LLM Agents in Interactive Environments

Competitive analysis of existing benchmarks that evaluate LLM agents in interactive text environments. Reference for positioning LLM-Quest.

## Summary

| Benchmark | Domain | Tasks | Agent Modes | Multi-agent | Metric | Lang |
|-----------|--------|-------|-------------|-------------|--------|------|
| **TextQuests** | Parser-based IF (Infocom classics) | 25 | 1 (with/without clues) | No | Progress % + Harm | EN |
| **TextArena** | Competitive text games (100+ games) | 99 | 1 (single-turn) | Yes | TrueSkill | EN |
| **AgentBench** | 8 diverse environments (OS, DB, web, games) | ~4K+ | 1 (API caller) | Limited | Success rate | EN (+ZH) |
| **AgentQuest** | 11 wrapped benchmarks (puzzles, QA, embodied) | Varies | Framework only | No | Success + Progress + Repetition | EN |
| **GameBench** | 9 board/card/social games | 9 | 3 (base/CoT/RAP) | Yes | Bradley-Terry rating | EN |
| **clembench** | Dialogue games (Wordle, Taboo, etc.) | Varies | Self-play | Yes | Task-specific | Multi |
| **SmartPlay** | 6 games (Minecraft, Hanoi, etc.) | 6 | Capability-isolated | No | 9 capability scores | EN |

## Detailed Profiles

### TextQuests (CAIS / HuggingFace, 2025) - Closest Competitor

- **Repo**: https://github.com/centerforaisafety/textquests
- **Paper**: https://arxiv.org/abs/2507.23701
- **Leaderboard**: https://huggingface.co/spaces/cais/textquests

Evaluates LLMs on 25 classic Infocom text adventures (Zork, Hitchhiker's Guide, etc.) via parser-based interaction. Tests sustained long-context reasoning: full game history maintained without truncation (100K+ tokens), no external tools allowed. Two modes: No Clues and With Clues (official InvisiClues).

**Top results**: GPT-5 leads at 37.8% (no clues) / 70.0% (with clues). Zero games fully completed without clues by any model. DeepSeek R1 at 15.2%, Llama 4 Scout at 4.8%.

**Strengths**: High-profile backing (CAIS, Dan Hendrycks), well-established game corpus, measures reasoning endurance over hundreds of steps.

**Gaps**: Single agent architecture (no tools/planning variants), English only, proprietary game ROMs required, email-based leaderboard submission.

---

### TextArena (2025)

- **Repo**: https://github.com/LeonGuertler/TextArena
- **Paper**: https://arxiv.org/abs/2504.11442
- **Leaderboard**: https://textarena.ai/leaderboard

Gym-style framework of 100+ text-based games for competitive, cooperative, and single-player evaluation. Games include chess, poker, Wordle, Diplomacy, Prisoner's Dilemma. 283 models on the online platform.

**Strengths**: Scale (100+ games), live platform with human play, TrueSkill ratings, pip-installable.

**Gaps**: Trivially simple agent interface (single-turn text in/out, no tools/planning/memory). English only. Many multi-player environments unfinished.

---

### AgentBench (Tsinghua, ICLR 2024)

- **Repo**: https://github.com/THUDM/AgentBench
- **Paper**: https://arxiv.org/abs/2308.03688

Multi-environment benchmark across 8 domains: OS interaction, databases, knowledge graphs, web shopping, web browsing, household tasks (ALFWorld), card game, lateral thinking puzzles. Docker-containerized task workers.

**Strengths**: First comprehensive multi-environment agent benchmark. Strong academic credibility (ICLR 2024). Breadth across very different interactive domains.

**Gaps**: Heavy infrastructure (multiple Docker images, 16GB+ RAM). No agent architecture variation - treats the agent as a fixed API caller. Codebase fragmented across v0.1/v0.2/FC versions.

---

### AgentQuest (NEC Research, NAACL 2024)

- **Repo**: https://github.com/nec-research/agentquest
- **Paper**: https://aclanthology.org/2024.naacl-demo.19.pdf

Meta-framework wrapping 11 existing academic benchmarks (MMLU, GSM8k, AlfWorld, WebShop, etc.) with unified metrics. Key contribution: progress rate (partial completion) and repetition rate (action redundancy) metrics beyond binary success/failure.

**Strengths**: Progress and repetition metrics provide nuanced agent behavior analysis. Agent-agnostic design.

**Gaps**: No results shipped - it's a framework with no published scores. 6 commits, minimal community. No Docker, no CI.

---

### GameBench (2024)

- **Repo**: https://github.com/Joshuaclymer/GameBench
- **Paper**: https://arxiv.org/abs/2406.06613
- **Site**: https://gamebench-website.vercel.app/

9 board/card/social games specifically chosen to be outside LLM training data. Tests 6 strategic reasoning axes: abstract strategy, non-deterministic outcomes, hidden information, language communication, social deduction, cooperation.

**Strengths**: Games outside pretraining corpora, rigorous Bradley-Terry statistical framework, tests genuine reasoning vs memorized strategies.

**Gaps**: Only GPT-3/4 tested. 21 stars, low adoption. No tool-augmented agents.

---

### Honorable Mentions

**SmartPlay** (Microsoft, ICLR 2024): 6 games testing 9 isolated agent capabilities. https://github.com/microsoft/SmartPlay

**clembench** (2024): Dialogue-game-based evaluation with self-play. Multilingual. Live leaderboard at https://clembench.github.io/

**LMRL-Gym** (Levine et al., ICML 2025): 8 multi-turn RL tasks for LLMs, focused on credit assignment and RL fine-tuning rather than prompting evaluation. https://github.com/abdulhaim/LMRL-Gym

## Gap in the Landscape

A consistent pattern across these benchmarks: they vary tasks and models but treat the agent as a black box. The model receives a prompt, returns an action. At most, one benchmark (GameBench) adds CoT as a variant.

No existing benchmark evaluates agent architecture as an independent dimension - comparing how the same model performs on the same task when given different cognitive scaffolding (planning loops, tool access, prompt strategies). This is the niche LLM-Quest targets: a 3D evaluation matrix of models x tasks x agent modes, on bilingual choice-based interactive fiction.
