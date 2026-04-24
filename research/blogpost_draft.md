# [TITLE TBD - after final experiments]

*[Substack post draft - target 1,000-1,200 words]*

---

I grew up playing Space Rangers 2 -- a sprawling space RPG from 2004 that somehow packed an RTS, a shooter, and a collection of text adventure quests into one game. The text quests were my favorite: you'd land on a planet, get dropped into a scenario (infiltrate a ministry, win a prison escape, deliver pizza under time pressure), and navigate it through a series of choices. No combat, no reflexes -- just reading comprehension and decision-making.

A year ago I started wondering whether LLMs could pass these quests. Each turn is just "read a situation, pick from a list of options" -- exactly the kind of task language models should be good at. So I built a benchmark: a Python harness that connects LLMs to the original quest engine, runs them through dozens of quests, and records whether they win or lose.

I've now run 3,600+ tests across a dozen models. The results were not what I expected.

## The setup

Each turn, the model receives a text description and a numbered list of actions. It picks one. The quest engine advances the state. Repeat for 10-50+ turns until the quest ends in success or failure.

```
Step 7
════════════════════════════════════════════
You stand in a hall with pink speckled wallpaper.
To the left the commandant's office, ahead a long corridor.
A sign reads: "Registry - Room 12"

Status: Dressed casually | 500 credits | No documents

Choices:
  1. Go to the commandant's office
  2. Walk down the corridor
  3. Check the registry
  4. Leave the building
```

The quests range from straightforward (gather items, talk to NPCs) to genuinely hard (sliding puzzles, resource optimization, bureaucratic mazes with dead ends). There are about 90 available in English and Russian.

## The punchline

Overall success rate across all models and configurations: **9.3%**.

For reference, an agent that picks randomly scores **11.3%**.

[TODO: Insert results table/chart after final experiment iteration]

Most mid-tier production models -- GPT-5.4 Mini, Gemini 3 Flash, Claude Haiku 4.5, DeepSeek V3.2, Mistral Medium, Minimax -- land somewhere between 5% and 12%. Barely distinguishable from a coin flip.

## Why: the loop trap

I classified 794 failed runs by failure mode. The breakdown:

| Failure Mode | % of Failures |
|---|---|
| **Repetition loops** | 71% |
| Bad strategy | 19% |
| Comprehension failure | 4% |
| Parse/format errors | 4% |
| Dead ends | 2% |

**Seven out of ten failures are loops.** The model visits a location, tries a few things, goes somewhere else, then comes right back. And again. And again. Here's Mistral Medium on a bureaucracy quest -- 921 steps, zero progress:

```
Step 10: You stand in a hall with pink wallpaper. → Go to commandant
Step 11: "How dare you speak without papers!" → Leave
Step 12: You stand in a hall with pink wallpaper. → Walk down corridor
Step 13: A clean corridor, bright with light. → Look out window
Step 14: Silly thoughts come to mind. → Go back
Step 15: A clean corridor. → Try a door
Step 16: The door is locked. → Go back
Step 17: A clean corridor. → Go to another room
Step 18: A thick bass voice: "Is it reserved?" → Leave
Step 19: A clean corridor. → Walk down corridor
Step 20: A green chandelier room. → Go back
  ... [901 more steps of this]
```

The model can read. It can pick valid actions. What it can't do is remember that it already tried this exact sequence three steps ago. It has no sense of "I'm going in circles" -- even when the quest text is literally identical to what it saw before.

This isn't a model-specific problem. **Every model** we tested has LOOP as its dominant failure mode. Claude, GPT, Gemini, DeepSeek, Mistral, Minimax -- all of them get stuck in the same way.

## What actually helps (hint: it's not smarter prompting)

The one architecture that clearly separates from random is the **planner mode**: before each action, the agent generates a multi-step plan, tracks progress against it, and replans when things change. Claude Sonnet 4.5 with the planner scaffolding hit ~18% success -- not amazing, but meaningfully above the random baseline.

That result pointed at something specific. The planner works not because it reasons better, but because it forces the model to write down its state. Which raised an obvious question: what if we just gave the model its full history?

## The fix: we gave the agent a memory

When I dug into the failure logs, I found something embarrassing. The default agent configuration uses a sliding context window of **3 observations**. The quest briefing -- mission goal, setting, success criteria -- is shown at step 0. By step 4, it's gone. The agent was playing quests without knowing what the quest asked it to do.

I started calling this the amnesia bug. It explains a lot. An agent that can't remember where it started can't know when it's going in circles.

The fix was to build three memory modes:

- **Default (3 obs, 5 decisions)**: the broken baseline
- **Full transcript**: every previous observation, choice, and reasoning step is appended to each prompt
- **Compaction**: every 10 steps, the agent writes a short summary of its progress; that summary travels with it instead of the raw history

No prompt engineering. No loop-detection heuristics. Just: give the agent its history.

## Results: from 0% to 100% in one config change

I ran all four configurations (the three memory modes plus a loop-aware reasoning variant) on two quests -- Pizza_eng and Ski_eng -- using Gemini 3 Flash, 3 runs each:

| Configuration | Pizza_eng | Ski_eng |
|---|---|---|
| Default memory (baseline) | 0/3 | 0/3 |
| Loop-aware reasoning + default memory | 0/3 | 1/3 |
| Full transcript memory | **3/3** | 0/3 |
| Compaction memory | **2/2** | pending |

Full transcript on Pizza_eng: 0% to 100%. No new model, no fine-tuning, no carefully crafted system prompt. Just memory.

The speed result surprised me more than the accuracy. I expected full transcript runs to be slower -- they send more tokens per request. They were actually faster: **55 seconds average vs. 80 seconds for the baseline**. An agent that knows where it's been doesn't wander. It solves the quest on the first coherent path instead of thrashing through dead ends for a hundred steps.

The loop-aware reasoning variant helped a little (1/3 on Ski_eng vs. 0/3 baseline) but couldn't overcome the amnesia. Knowing you might be in a loop is less useful than actually remembering the last ten turns.

## What's next

Ski_eng is the interesting frontier. Even with full transcript memory, 0/3. The quest requires something memory alone doesn't provide -- likely domain-specific strategy or committing to a multi-step plan and not abandoning it when the path gets uncomfortable. That's a different problem, and a harder one.

Compaction mode is worth watching. It scales better than full transcript for long quests (fewer tokens, no context-window blowout), and early results on Pizza suggest it's competitive. The open question is whether the summaries lose critical detail that matters later.

The deeper finding is structural: if amnesia is responsible for most of the 71% loop rate, fixing memory should move the overall benchmark number significantly. I'll run the full quest set with full transcript and report back.

A few other threads I want to pull on:

- Why do human difficulty ratings not predict LLM success? (They don't -- I checked.)
- Can compaction be made quest-adaptive, summarizing more aggressively when nothing is changing?
- What does the failure distribution look like after memory is fixed? Is "bad strategy" the next dominant mode?

## Try it yourself

The benchmark is fully open source. You can:
- [Browse the live leaderboard](https://yourconscience.github.io/llm_quest_benchmark/)
- [Read the methodology](https://yourconscience.github.io/llm_quest_benchmark/about.html)
- Test your own model or memory configuration with a single config change:

```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark
docker compose run llm-quest run --quest quests/Boat.qm --model your-model-here
```

If you're working on agent architectures or LLM evaluation, I'd love to hear what you think. The quest corpus is a useful testbed precisely because the tasks weren't designed for LLMs -- the difficulty is organic, not synthetic, and the failure modes are revealing.

---

*[Kirill Korikov](https://linkedin.com/in/kirill-korikov-a19180101) is a Senior ML Engineer who builds LLM infrastructure and evaluation systems. Previously at Inworld AI.*
