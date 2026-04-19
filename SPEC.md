# SPEC: LLM-Quest

An agentic benchmark for evaluating LLM decision-making in text-based quest environments.

## Goal

Build a reproducible, multi-provider benchmark that measures how well LLM agents complete interactive fiction quests under varying agent architectures. Publish results as a static leaderboard site and a data-driven blog post styled as a short research paper.

The benchmark compares five agent modes across providers and quest difficulty levels, measuring success rate, quest progress, and decision quality on structured text quests.

Most agent benchmarks vary tasks and models but treat the agent as a black box. LLM-Quest adds agent architecture as a first-class evaluation dimension: the same model on the same quest produces different outcomes depending on whether it reasons step-by-step, plans ahead, has domain knowledge, or uses tools. The benchmark is a 3D matrix - models x quests x agent modes - across providers and languages. See `research/LANDSCAPE.md` for competitive analysis.

## Non-goals

- Full RAG pipeline with vector DB (potential follow-up). Lightweight knowledge injection is in scope as Mode C.
- Runtime web UI. The existing Flask app is removed entirely - the interface is CLI + YAML config.
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

Required providers for the leaderboard (one model per family minimum):
- OpenAI (GPT-5 or GPT-5-mini)
- Anthropic (Claude Sonnet 4.5 or later)
- Google (Gemini 2.5 Flash or Pro)
- DeepSeek (deepseek-3.2-chat or reasoner)

Optional (stretch): Qwen, GLM.

## Architecture changes

### Remove Flask web UI

Delete `llm_quest_benchmark/web/` and all Flask dependencies. The web UI is replaced by:
- CLI commands for running experiments (`llm-quest run`, `llm-quest benchmark`).
- YAML config files for defining benchmark matrices.
- Static site for publishing results.

### CLI interface

```
llm-quest download-quests          # runs download_quests.sh, validates corpus
llm-quest run --quest X --agent-mode B --model gpt-5-mini
llm-quest benchmark --config configs/benchmarks/full_matrix.yaml
llm-quest report --benchmark-id <ID> --format md
llm-quest leaderboard --output site/data/leaderboard.json
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
- Data source: `site/data/leaderboard.json` generated by `llm-quest leaderboard` from benchmark results.

### Blog post

- Part of the static site, not a separate publication.
- Styled as a short research paper: abstract, introduction, method, results, discussion, limitations.
- Central claim: determined by data. Run the full benchmark matrix first, then write the narrative around the strongest finding.
- Minimum content: method description, results tables, at least one chart, honest discussion of limitations.

## Acceptance criteria

All criteria must be met for the spec to be considered complete:

1. **Leaderboard deployed**: Static site on GitHub Pages showing results from at least 4 provider families (OpenAI, Anthropic, Google, DeepSeek).
2. **Mode comparison**: Results table comparing all 5 agent modes (A-E) across providers.
3. **Performance bar**: Best model + agent mode combination achieves >= 80% success rate on at least 10 different quests. If no config hits 80% success, report progress % as the primary metric and explain the ceiling (TextQuests found zero models completing any game without clues - an honest null result is still publishable).
4. **Corpus scale**: 50+ working quests in the corpus, each with >= 20 non-zero completion attempts in published results.
5. **Reproducibility**: Full benchmark can be reproduced from a clean clone with `uv` or Docker via a single documented command.
6. **Blog post**: Published on the project site with method, results, and discussion sections.
7. **Flask removed**: No Flask dependencies remain in the project.

## Constraints

- **Runtime**: Python 3.11+, managed with `uv`. TypeScript quest engine via existing bridge.
- **Cost**: LLM API calls cost real money. The full matrix (5 modes x 4+ providers x 50+ quests x 20+ runs) is expensive. Design configs for incremental runs: single-quest smoke test, single-provider sweep, full matrix.
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
4. **Cost of full matrix**: 5 modes x 4 providers x 50 quests x 20 runs = 20,000 LLM calls minimum. With knowledge gradient sub-levels (C0-C3), the full matrix is larger. Estimate cost before committing. Run cheapest models/modes first.
5. **Mode D/E complexity**: Planner and tool-augmented agents are new code. Scope creep risk - keep implementations shallow and iterate.
6. **Models may not complete quests at all**: TextQuests (2025) found zero models completing any Infocom game without clues. Our quests are shorter and choice-based (easier), but the same ceiling effect is possible. Progress % and the knowledge gradient provide a publishable story even if success rates are low.
7. **TextQuests differentiation**: HuggingFace's TextQuests (2025) is the closest competitor. Key differentiators: agent architecture comparison (5 modes vs 1), bilingual RU/EN, choice-based vs parser-based IF, knowledge gradient experiment. Lead with "vary the agent, not the task" framing.

## Codebase notes

- Prompt templates: `llm_quest_benchmark/prompt_templates/*.jinja` - modes A/B reuse these.
- Agent implementations: `llm_quest_benchmark/agents/` - modes D/E add new agent classes here.
- Benchmark configs: `configs/benchmarks/*.yaml` - add new configs for the full matrix.
- Quest outcome: `llm_quest_benchmark/environments/state.py:QuestOutcome` - binary SUCCESS/FAILURE already implemented.
- Existing CLI: `llm_quest_benchmark/executors/cli/commands.py` - extend with new commands.
- Flask code to remove: `llm_quest_benchmark/web/` (entire directory).

## Phases

### Phase 1: Foundation
- Download and validate quest corpus (run `download_quests.sh`, count working quests per language).
- Remove Flask web UI and dependencies.
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

## Outcome / Deviations

_To be filled after implementation._
