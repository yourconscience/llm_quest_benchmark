# SPEC: LLM-Quest

An agentic benchmark for evaluating LLM decision-making in text-based quest environments.

## Goal

Build a reproducible, multi-provider benchmark that measures how well LLM agents complete interactive fiction quests under varying agent architectures. Publish results as a static leaderboard site and a data-driven blog post styled as a short research paper.

The benchmark compares five agent modes across providers and quest difficulty levels, measuring success rate, quest progress, and decision quality on structured text quests.

Most agent benchmarks vary tasks and models but treat the agent as a black box. LLM-Quest adds agent architecture as a first-class evaluation dimension: the same model on the same quest produces different outcomes depending on whether it reasons step-by-step, plans ahead, has domain knowledge, or uses tools. The benchmark is a 3D matrix - models x quests x agent modes - across providers and languages. See `research/LANDSCAPE.md` for competitive analysis.

## Non-goals

- Full RAG pipeline with vector DB (potential follow-up). Lightweight knowledge injection is in scope as Mode C.
- Runtime web UI. The interface is CLI + YAML config.
- New quest authoring or quest format changes. Quests come from upstream Space Rangers archives via `download_quests.sh`.
- Competing with TextQuests (HuggingFace) or TextArena on their turf. LLM-Quest focuses on structured quests with clear success/failure, not open-ended IF or adversarial games.

## Benchmark design

### Quest corpus

- **Source**: Space Rangers `.qm`/`.qmm` quest files, downloaded from GitLab upstream.
- **Languages**: Bilingual RU/EN. Minimum 35 English quests + 1-2 Russian collections of comparable size.
- **Qualification**: A quest is "working" if it can be loaded by the TypeScript engine, has at least one reachable success ending, and has been completed at least once by any agent or human.
- **Target**: 50+ working quests total, each with 20+ non-zero completion attempts in the final results.

### Evaluation metrics

Inspired by TextQuests (CAIS, 2025) and AgentQuest (NEC, NAACL 2024). See `research/LANDSCAPE.md`.

**Primary metrics** (reported on leaderboard):
- **Success rate** (%) = successful completions / total attempts per quest per agent config.
- **Quest progress** (%) = fraction of labeled checkpoints reached, averaged across attempts. Measures how far the agent gets even on failed runs. Requires checkpoint labeling per quest (see Risks).

**Secondary metrics** (reported in blog post / detailed results):
- **Avg steps to completion**: How efficiently the agent solves a quest.
- **Repetition rate**: Fraction of steps where the agent repeats a recently taken action (Levenshtein similarity threshold). Borrowed from AgentQuest - measures wasted effort and loop behavior.
- **Bad decision rate**: Fraction of choices that lead to immediate failure states or dead ends.
- **Token cost per run**: Average API cost in USD.
- **Timeout rate**: Fraction of runs that hit the step limit without resolution.

**Outcome model**: Binary at the quest level. `QuestOutcome.SUCCESS` (1) vs `QuestOutcome.FAILURE` (0). Error/timeout runs are excluded from success rate but reported separately. Progress % provides a continuous signal for failed runs.

### Agent modes

| Mode | ID | Description |
|------|----|-------------|
| Baseline | `A` | Single-step, minimal prompt. Picks an action number with no reasoning. |
| Prompted | `B` | Existing reasoning/strategic/loop-aware templates. The agent analyzes options and reasons about consequences. |
| Knowledge | `C` | Domain knowledge injected into context. See knowledge gradient below. Same decision loop as B. |
| Planner | `D` | Multi-step planning agent. Maintains a plan, re-plans when the situation changes, then picks an action aligned with the plan. |
| Tool-augmented | `E` | Agent has access to tools: quest history (memory of past quest states within the same quest). Calculator and domain knowledge lookup deferred to future PRs. |

### Knowledge gradient (Mode C levels)

Knowledge injection is a dimension, not a binary toggle. Tested as sub-levels of Mode C:

| Level | Tag | What's injected | Effort |
|-------|-----|-----------------|--------|
| C0 | `no-knowledge` | Nothing (same as Mode B, control group) | None |
| C1 | `light-hints` | General quest mechanics and game rules (static, quest-agnostic) | Low |
| C2 | `heavy-context` | Quest-specific hints, walkthrough fragments, or known-good strategies | Medium |
| C3 | `rag` | Retrieval from a knowledge base of past runs, quest descriptions, and game lore | High |

**Priority**: C1 first (cheap, high signal). C2 if C1 shows improvement. C3 is stretch goal only - requires building an embedding index and retrieval pipeline.

The C1-vs-C0 delta is the "does knowledge help?" finding. The C2-vs-C1 delta measures diminishing returns of heavier context. C3 tests whether retrieval beats manually curated knowledge.

### Provider matrix

Mid-tier models: we benchmark the "Sonnet-equivalent" production tier for each provider - the models most developers actually use. This keeps per-run cost in the $0.01-0.04 range and makes the comparison fair (similar capability/price class). High-tier comparison (Claude Sonnet, GPT-5.4, Gemini Pro) is a planned follow-up.

**Primary (6 models, all via OpenRouter, Arena ELO 1403-1474):**

| Provider | Model | OpenRouter ID | In $/1M | Out $/1M | Arena ELO |
|---|---|---|---|---|---|
| Google | Gemini 3 Flash | `google/gemini-3-flash-preview` | $0.50 | $3.00 | 1474 |
| OpenAI | GPT-5.4 Mini | `openai/gpt-5.4-mini` | $0.75 | $4.50 | 1458 |
| DeepSeek | V3.2 | `deepseek/deepseek-v3.2` | $0.26 | $0.42 | 1424 |
| Mistral | Medium 3.1 | `mistralai/mistral-medium-3.1` | $0.40 | $2.00 | 1410 |
| Anthropic | Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | $1.00 | $5.00 | 1408 |
| Minimax | M2.5 | `minimax/minimax-m2.5` | $0.12 | $0.99 | 1403 |

Selection rationale: one model per major provider, mid-tier production class (ELO 1400-1475), all tested for speed and reliability via OpenRouter. Qwen excluded (all recent models too slow on OpenRouter routing). Kimi K2.5 and GLM-5 excluded (latency and parse reliability issues on OpenRouter).

**Excluded from main benchmark (high-tier, follow-up):**
- Anthropic Claude Sonnet 4.6 ($3/$15) - frontier tier
- OpenAI GPT-5.4 ($1.25/$10) - frontier tier
- Google Gemini 3 Pro - frontier tier

### Run budget

3 runs per cell (model x quest x mode). Comparable papers use 3-5: TextQuests used 3, AgentQuest used 5. Binary outcomes don't need large N per cell - breadth across quests and modes matters more than depth per combination. Targeted 10-run follow-ups on specific cells where tighter confidence intervals are needed.

**Phase 1 (baseline re-run with telemetry):** 17 quests x 6 models x 2 modes (A+B) x 3 runs = ~612 runs, ~$14
**Phase 2 (intervention runs):** 10 hard quests x 3 best models x 3 modes (C/D/E) x 3 runs = ~270 runs, ~$6
**Phase 3 (new quests):** 18 untested EN quests x 4 models x mode B x 3 runs = ~216 runs, ~$5
**Total: ~1100 runs, ~$25**

## Architecture changes

### CLI interface

```
llm-quest download-quests          # runs download_quests.sh, validates corpus
llm-quest run --quest X --agent-mode B --model gpt-5-mini
llm-quest benchmark --config configs/benchmarks/full_matrix.yaml
llm-quest report --benchmark-id <ID> --format md
llm-quest leaderboard --output site/leaderboard.json
```

### Agent mode implementation

- Modes A and B: already exist (stub.jinja, reasoning.jinja, strategic.jinja, etc.).
- Mode C (levels C0-C3): C0 is Mode B (control). C1: new template with general game mechanics block prepended (static YAML). C2: quest-specific hints curated manually. C3 (stretch): RAG retrieval from an embedding index of past runs and game lore.
- Mode D: new agent class wrapping the LLM client with a plan-maintain-act loop. Plan is text, re-evaluated every N steps or on significant state change.
- Mode E: new agent class with tool-use support. Tools are simple Python functions registered as available actions alongside the quest options.

### Static site

- Stack: Hugo, MkDocs-Material, or plain HTML/JS - whatever generates a clean single-page benchmark site from JSON data.
- Hosted on GitHub Pages from a `docs/` or `site/` directory in the repo.
- Content:
  - Leaderboard table: model x agent mode, sortable by success rate.
  - Quest difficulty distribution chart.
  - Per-quest breakdown (expandable or linked).
  - Blog post / research write-up as a page on the same site.
- Data source: `site/leaderboard.json` generated by `llm-quest leaderboard` from benchmark results.

### Blog post

- Part of the static site, not a separate publication.
- Styled as a short research paper: abstract, introduction, method, results, discussion, limitations.
- Central claim: determined by data. Run the full benchmark matrix first, then write the narrative around the strongest finding.
- Minimum content: method description, results tables, at least one chart, honest discussion of limitations.

## Acceptance criteria

All criteria must be met for the spec to be considered complete:

1. **Leaderboard deployed**: Static site on GitHub Pages showing results from at least 6 provider families.
2. **Mode comparison**: Results table comparing agent modes A-B (all quests) and C/D/E (hard quests) across providers.
3. **Performance bar**: Best model + agent mode combination achieves >= 80% success rate on at least 10 different quests. If no config hits 80% success, report progress % as the primary metric and explain the ceiling (TextQuests found zero models completing any game without clues - an honest null result is still publishable).
4. **Corpus scale**: 35+ working EN quests in the corpus, each with >= 3 completion attempts per model in published results.
5. **Reproducibility**: Full benchmark can be reproduced from a clean clone with `uv` or Docker via a single documented command.
6. **Blog post**: Published on the project site with method, results, and discussion sections.
7. **CLI-first benchmark runtime**: Benchmark execution remains CLI + YAML driven; static site assets are generated for publication and play mode.

## Constraints

- **Runtime**: Python 3.11+, managed with `uv`. TypeScript quest engine via existing bridge.
- **Cost**: LLM API calls cost real money. The full matrix (~1100 runs across 6 mid-tier models) is estimated at ~$25. Design configs for incremental runs: single-quest smoke test, single-provider sweep, full matrix.
- **Quest files**: Not committed to repo. Downloaded via `download_quests.sh`. CI/CD must handle this.
- **Determinism**: LLM outputs are non-deterministic. Success rates are statistical. Report confidence intervals or at minimum the number of attempts.

## Dependencies / integrations

- `space-rangers-quest` TypeScript submodule (quest engine, already integrated).
- LLM provider SDKs: `openai`, `anthropic`, `google-generativeai`, existing in project.
- Static site generator: TBD (Hugo, MkDocs-Material, or custom).
- GitHub Pages: deployment target.

## Risks / open questions

1. **English quest count**: Need to verify that `download_quests.sh` yields 35+ distinct working English quests. If not, options: translate Russian quests, source additional IF quests, or lower the threshold.
2. **Quest success detection**: Some quests may have ambiguous endings. Need a human pass to label which endings count as success vs failure for edge cases.
3. **Checkpoint labeling for progress %**: Progress metric requires defining intermediate checkpoints per quest. The .qm format has location/state data that may be extractable, but manual validation is needed. Start with 10 quests, then scale.
4. **Cost of full matrix**: ~1200 runs at ~$27 for 7 mid-tier models. High-tier follow-up (Claude Sonnet, GPT-5.4, Gemini Pro) adds ~$50-100 depending on scope.
5. **Mode D/E complexity**: Planner and tool-augmented agents are new code. Scope creep risk - keep implementations shallow and iterate.
6. **Models may not complete quests at all**: TextQuests (2025) found zero models completing any Infocom game without clues. Our quests are shorter and choice-based (easier), but the same ceiling effect is possible. Progress % and the knowledge gradient provide a publishable story even if success rates are low.
7. **TextQuests differentiation**: HuggingFace's TextQuests (2025) is the closest competitor. Key differentiators: agent architecture comparison (5 modes vs 1), bilingual RU/EN, choice-based vs parser-based IF, knowledge gradient experiment. Lead with "vary the agent, not the task" framing.

## Agent response protocol

All agents return structured JSON. The canonical response schema:

```json
{"memo": "<max 20 words>", "reasoning": "<max 25 words>", "result": <action_number>}
```

Fields:
- `memo` - Short state tracker maintained across turns. Agents use this to track inventory, health, codes, quest phase, and anything else worth remembering. Max 20 words. This is the **single** key for all state tracking: no aliases (`subgoal`, `state_notes`, etc.).
- `reasoning` - Brief explanation for the choice. Max 25 words.
- `analysis` - Optional deeper analysis (used by some templates).
- `result` - 1-based action number.

The `memo` field is stored in decision history, passed through compaction, and displayed in trace views. Templates that use state tracking must use this key.

## Codebase notes

- Prompt templates: `llm_quest_benchmark/prompt_templates/*.jinja` - modes A/B reuse these.
- Agent implementations: `llm_quest_benchmark/agents/` - modes D/E add new agent classes here.
- Benchmark configs: `configs/benchmarks/*.yaml` - add new configs for the full matrix.
- Quest outcome: `llm_quest_benchmark/environments/state.py:QuestOutcome` - binary SUCCESS/FAILURE already implemented.
- Existing CLI: `llm_quest_benchmark/executors/cli/commands.py` - extend with new commands.

## Phases

### Phase 1: Foundation
- Download and validate quest corpus (run `download_quests.sh`, count working quests per language).
- Implement progress % metric: extract location/state data from quest engine, label checkpoints for 10 pilot quests.
- Implement repetition rate metric.
- Ensure modes A and B run cleanly on 10+ quests across 2+ providers with all metrics reported.
- Set up static site scaffold with placeholder leaderboard.

### Phase 2: Agent modes C-E
- Implement Mode C level C1 (light knowledge hints) first. Run A vs B vs C1 on pilot quests.
- If C1 shows improvement, implement C2 (heavy context with quest-specific hints).
- Implement planner agent (mode D).
- Implement tool-augmented agent (mode E).
- Validate each mode on a small quest subset before scaling.
- Estimate cost for full matrix based on pilot results.

### Phase 3: Full benchmark
- Label checkpoints for all 50+ quests (progress % requires this).
- Run complete matrix: modes A-E x 4 providers x 50+ quests x 20+ attempts.
- If budget allows, run C3 (RAG) on a subset.
- Generate leaderboard JSON from results.
- Populate static site with real data.

### Phase 4: Publication
- Analyze results, identify strongest finding. Candidates:
  - "Agent architecture matters more than model choice"
  - "Knowledge unlocks quests that reasoning alone cannot solve"
  - "Frontier models plateau on easy quests but diverge on hard ones"
  - "No model completes hard quests without knowledge" (null result, still publishable)
- Write blog post with method, results, discussion.
- Deploy site to GitHub Pages.
- Update README to lead with benchmark framing.

## Current implementation status

- **Interface**: CLI + YAML config for benchmark execution; static GitHub Pages site for publication and play mode.
- **Agent modes**: A (baseline), B (prompted), C (knowledge/light hints), D (planner), E (tool-augmented) implemented.
- **Memory modes**: `full_transcript` and `compaction` (configurable interval).
- **LLM client**: OpenAI-compatible SDK with `timeout=30`, `max_retries=0`. All providers routed via OpenRouter.
- **Metrics**: Success rate, token cost, step count, and repetition rate implemented. Progress % remains future work.
