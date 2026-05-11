# Harness Engineering

LLM Quest Benchmark treats the **agent harness** as the primary experimental
object. An agent harness is the wrapper around a model that controls what the
model sees, what state is carried forward, what external tools are available,
and how a raw model completion is converted into a quest action. In this
project, harnesses are not incidental plumbing: they are the independent
variable.

This framing follows the harness engineering question raised by "How Much Heavy
Lifting Can an Agent Harness Do?" (arXiv:2604.07236): how much performance comes
from the surrounding scaffold rather than the base model alone? Space Rangers
text quests are a useful testbed because they are long enough to stress memory,
planning, and state tracking, but concrete enough to score with terminal
success/failure outcomes.

## The Eight Canonical Harnesses

| Harness name | What varies |
|---|---|
| `minimal` | Uses the smallest action-selection prompt with recent context only. This is the low-scaffold baseline. |
| `reasoning_recent` | Adds an explicit reasoning prompt while keeping recent-window memory. |
| `reasoning_full` | Keeps the reasoning prompt but exposes the full transcript instead of a short recent window. |
| `memo_compact` | Uses compacted memory plus a constrained 20-word memo to preserve salient state. |
| `hinted_compact` | Adds mechanics hints to the compact memo harness, without tools. |
| `tool_compact` | Adds calculator, scratchpad, and quest-history tools to compact memory. |
| `tool_hinted` | Combines compact memory, tools, and mechanics hints. |
| `planner` | Uses a plan-maintain-act loop with compact memory instead of a pure react loop. |

The harness names are canonical snake_case identifiers used in YAML configs,
the CLI, and documentation. Public labels can be friendlier, but experimental
records should preserve these names so runs remain comparable.

## Difference From TextQuests and TALE-Suite

TextQuests (arXiv:2507.23701) and TALE-Suite are closest in spirit because they
also evaluate language models on interactive text-game tasks. Their main
comparison axis is model capability under a mostly fixed evaluation scaffold:
the harness is treated as test infrastructure, and the model is varied.

LLM Quest Benchmark flips that emphasis. We can hold a model fixed and vary the
harness to ask which context, memory, tool, and planning choices change
behavior. That makes the benchmark useful for harness engineering: it can
separate "the model cannot do the task" from "this wrapper failed to show the
model the right state, preserve the right facts, or expose the right operation."

## Findings So Far

The strongest pattern so far is that bigger scaffolds are not automatically
better. A concise 20-word memo produced a sweet spot: it improved over no memo
and full transcript baselines, while longer or more structured memo variants
regressed. The likely mechanism is selective pressure: the short memo forces
the harness to preserve only state that matters for future decisions.

Tools and hints show a synergy effect. Prompt hints alone hurt, and tools alone
were modest, but tools plus hints improved outcomes because the hints pointed
the model toward quantities and morally grey quest mechanics while the
calculator, scratchpad, and history search gave it ways to act on those
signals.

Verbosity hurts in this environment. Some newer or larger models timed out more
often because they spent too much of the quest budget generating long step
responses. For sequential decision tasks, a harness that elicits concise,
actionable state updates can outperform one that invites broad reasoning.
