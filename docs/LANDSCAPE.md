# Benchmark Landscape: LLM Agents in Interactive Environments

Competitive analysis for LLM-Quest. Last updated: 2026-04-17.

## Summary

| Benchmark | Domain | Tasks | Agent Modes | Multi-agent | Providers Tested | Metric | Leaderboard | Lang |
|-----------|--------|-------|-------------|-------------|-----------------|--------|-------------|------|
| **LLM-Quest** (ours) | Choice-based IF (Space Rangers .qm) | 50+ target | 5 (baseline/prompted/knowledge/planner/tools) | No | 4+ (OpenAI, Anthropic, Google, DeepSeek) | Binary success rate | Planned (GitHub Pages) | RU/EN |
| **TextQuests** | Parser-based IF (Infocom classics) | 25 | 1 (with/without clues) | No | 10+ frontier models | Progress % + Harm | HuggingFace Space | EN |
| **TextArena** | Competitive text games (100+ games) | 99 | 1 (single-turn) | Yes | 283 models on platform | TrueSkill | textarena.ai | EN |
| **AgentBench** | 8 diverse environments (OS, DB, web, games) | ~4K+ | 1 (API caller) | Limited (Avalon) | 29 (GPT-4, Claude, open-source) | Success rate | Google Sheets | EN (+ZH) |
| **AgentQuest** | 11 wrapped benchmarks (puzzles, QA, embodied) | Varies | Agent-agnostic framework | No | None shipped | Success + Progress + Repetition | No | EN |
| **GameBench** | 9 board/card/social games | 9 | 3 (base/CoT/RAP) | Yes | GPT-3, GPT-4 only | Bradley-Terry rating | Minimal static site | EN |
| **clembench** | Dialogue games (Wordle, Taboo, etc.) | Varies | Self-play | Yes (dialogue) | Multiple | Task-specific | clembench.github.io | Multi |
| **SmartPlay** | 6 games (Minecraft, Hanoi, etc.) | 6 | Capability-isolated | No | Multiple | 9 capability scores | No | EN |

## Detailed Profiles

### TextQuests (CAIS / HuggingFace, 2025) - Closest Competitor

- **Repo**: https://github.com/centerforaisafety/textquests
- **Paper**: https://arxiv.org/abs/2507.23701
- **Leaderboard**: https://huggingface.co/spaces/cais/textquests

Evaluates LLMs on 25 classic Infocom text adventures (Zork, Hitchhiker's Guide, etc.) via parser-based interaction. Tests sustained long-context reasoning: full game history maintained without truncation (100K+ tokens), no external tools allowed. Two modes: No Clues and With Clues (official InvisiClues).

**Top results**: GPT-5 leads at 37.8% (no clues) / 70.0% (with clues). Zero games fully completed without clues by any model. DeepSeek R1 at 15.2%, Llama 4 Scout at 4.8%.

**Key strength**: High-profile backing (CAIS, Dan Hendrycks), well-established game corpus, measures reasoning endurance over hundreds of steps.

**Key weakness**: Single agent architecture (no tools/planning variants), English only, proprietary game ROMs required, email-based leaderboard submission.

**Differentiation from LLM-Quest**: TextQuests measures raw reasoning endurance in parser IF. LLM-Quest measures decision quality under varying agent architectures in choice-based IF. TextQuests has one agent mode; LLM-Quest has five. TextQuests is English-only; LLM-Quest is bilingual. Complementary rather than competing.

---

### TextArena (2025)

- **Repo**: https://github.com/LeonGuertler/TextArena
- **Paper**: https://arxiv.org/abs/2504.11442
- **Leaderboard**: https://textarena.ai/leaderboard

Gym-style framework of 100+ text-based games for competitive, cooperative, and single-player evaluation. Games include chess, poker, Wordle, Diplomacy, Prisoner's Dilemma. 283 models on the online platform.

**Key strength**: Scale (100+ games), live platform with human play, TrueSkill ratings, pip-installable.

**Key weakness**: Trivially simple agent interface (single-turn text in/out, no tools/planning/memory). English only. Many multi-player environments unfinished.

**Differentiation from LLM-Quest**: TextArena goes wide (100+ games, adversarial multi-agent). LLM-Quest goes deep (agent architecture comparison on narrative quests). TextArena has no agent mode variation; LLM-Quest has five. No overlap in task domain.

---

### AgentBench (Tsinghua, ICLR 2024)

- **Repo**: https://github.com/THUDM/AgentBench
- **Paper**: https://arxiv.org/abs/2308.03688

Multi-environment benchmark across 8 domains: OS interaction, databases, knowledge graphs, web shopping, web browsing, household tasks (ALFWorld), card game, lateral thinking puzzles. Docker-containerized task workers with controller-worker architecture.

**Key strength**: First comprehensive multi-environment agent benchmark. Strong academic credibility (ICLR 2024). Breadth across very different interactive domains. Function-calling support in FC version.

**Key weakness**: Heavy infrastructure (multiple Docker images, 16GB+ RAM, Freebase data). No agent architecture variation - treats the agent as a fixed API caller. Codebase fragmented across v0.1/v0.2/FC versions.

**Differentiation from LLM-Quest**: AgentBench is much broader (8 environments) but far heavier to run and doesn't explore agent design. LLM-Quest is lightweight, focused, and explicitly compares agent architectures on the same domain.

---

### AgentQuest (NEC Research, NAACL 2024)

- **Repo**: https://github.com/nec-research/agentquest
- **Paper**: https://aclanthology.org/2024.naacl-demo.19.pdf

Meta-framework wrapping 11 existing academic benchmarks (MMLU, GSM8k, AlfWorld, WebShop, etc.) with unified metrics. Key contribution: progress rate (partial completion) and repetition rate (action redundancy) metrics beyond binary success/failure.

**Key strength**: Progress and repetition metrics provide nuanced agent behavior analysis. Agent-agnostic design.

**Key weakness**: No results shipped - it's a framework with no published scores. 6 commits, minimal community. No Docker, no CI. OpenAI-only examples.

**Differentiation from LLM-Quest**: AgentQuest's progress/repetition metrics are interesting but the project ships no actual results. LLM-Quest ships concrete benchmark data. No domain overlap.

---

### GameBench (2024)

- **Repo**: https://github.com/Joshuaclymer/GameBench
- **Paper**: https://arxiv.org/abs/2406.06613
- **Site**: https://gamebench-website.vercel.app/

9 board/card/social games specifically chosen to be outside LLM training data. Tests 6 strategic reasoning axes: abstract strategy, non-deterministic outcomes, hidden information, language communication, social deduction, cooperation.

**Key strength**: Games outside pretraining corpora, rigorous Bradley-Terry statistical framework, tests genuine reasoning vs memorized strategies.

**Key weakness**: Only GPT-3/4 tested. 21 stars, low adoption. No tool-augmented agents.

**Differentiation from LLM-Quest**: GameBench tests adversarial strategic reasoning; LLM-Quest tests narrative decision-making. GameBench has a more rigorous statistical framework but far narrower model coverage. Minimal overlap.

---

### Honorable Mentions

**SmartPlay** (Microsoft, ICLR 2024): 6 games testing 9 isolated agent capabilities. https://github.com/microsoft/SmartPlay

**clembench** (2024): Dialogue-game-based evaluation with self-play. Multilingual. Live leaderboard at https://clembench.github.io/

**LMRL-Gym** (Levine et al., ICML 2025): 8 multi-turn RL tasks for LLMs, focused on credit assignment and RL fine-tuning rather than prompting evaluation. https://github.com/abdulhaim/LMRL-Gym

## LLM-Quest Positioning

Based on this landscape, LLM-Quest occupies a distinct niche:

**What no other benchmark does:**
1. **Agent architecture as an evaluation dimension.** Every other benchmark treats the agent as a black box (or at most adds CoT). LLM-Quest evaluates a 3D matrix: models x quests x agent modes. Five agent architectures (baseline through tool-augmented) are compared across providers and quest difficulties, isolating the impact of planning, tools, and domain knowledge.
2. **Bilingual evaluation.** All competitors are English-only (AgentBench has one Chinese variant). LLM-Quest evaluates on both Russian and English quests, testing cross-lingual decision-making.
3. **Choice-based interactive fiction.** TextQuests uses parser IF (typed commands); TextArena uses game-mechanical interactions. LLM-Quest uses structured choice-based quests (.qm format) with branching narratives - a middle ground between parser IF complexity and game-board simplicity.

**Where LLM-Quest is weaker:**
1. **Scale**: TextArena has 100+ games, AgentBench has 8 environments. LLM-Quest has 1 domain.
2. **Profile**: TextQuests has CAIS backing and a HuggingFace leaderboard. AgentBench has an ICLR 2024 paper. LLM-Quest is an independent project.
3. **Multi-agent**: TextArena and GameBench support adversarial play. LLM-Quest is single-agent only.

**Recommended narrative angle for the blog post:**
"Most agent benchmarks vary tasks and models but treat the agent as a black box. LLM-Quest adds agent architecture as a first-class evaluation dimension: the same model on the same quest produces different outcomes depending on whether it reasons step-by-step, plans ahead, has domain knowledge, or uses tools. The benchmark is a 3D matrix - models x quests x agent modes - across providers and languages."
