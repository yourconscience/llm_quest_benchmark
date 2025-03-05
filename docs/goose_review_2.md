# Improve Guide

The following tasks outline specific steps for a software engineer (SWE) to enhance our Sonnet-3.5-based LLM agent and achieve better success rates across text quests. These tasks focus on a chain-of-thought strategy, while remaining quest-agnostic.

---

## 1. Implement Generic Chain-of-Thought Prompting

1. **Add a Reasoning Template**
   - Create or modify an existing `reasoning.jinja` with the following:
     - Clear instruction to the agent: “Explain your plan in a `reasoning` field, then provide the numeric `action`.”
     - Strict JSON output that includes `{ "action": <number>, "reasoning": "..." }`.
   - Ensure no direct references to puzzle-specific solutions (like the 1-2-5-10 crossing).

2. **Integrate in `LLMAgent`**
   - Reference the new template in `LLMAgent.__init__` when chain-of-thought is enabled.
   - In `get_action`, parse the JSON to extract `action` and log or store `reasoning`.

3. **Parse Weaker Responses**
   - Extend or reuse `parse_llm_response` to handle partially valid or invalid JSON.
   - Fallback to action `1` in error cases.

---

## 2. Create Configurable Reasoning Steps

1. **Single-Step vs. Multi-Step**
   - In `strategic_agent.py` or a new class:
     - Provide a toggled path for "one-turn immediate action" vs. "two-phase think-then-decide."
   - Expose a parameter `use_advanced_reasoning` (boolean) that the user can set.

2. **Adaptive Approach**
   - If needed, add logic that for each quest run, if the quest is short or if the user sets `use_advanced_reasoning=False`, it reverts to a simpler flow.

3. **Integrate with CLI**
   - Let `llm-quest run` accept an extra flag (e.g., `--advanced-reasoning true/false`).
   - Translate that to the agent config.

---

## 3. Enhance Logging of Reasoning

1. **Modify `QuestStep`**
   - Add a `reasoning` or `llm_reasoning` field in the data class.
   - Store the chain-of-thought or partial “reasoning” produced by the LLM.

2. **Modify `QuestLogger.log_step`**
   - Accept the new `reasoning` field.
   - Optionally, keep it out of final user-facing logs if it’s too verbose.

3. **Validate Steps**
   - Confirm the debug logs capture the chain-of-thought.
   - Keep the environment output numeric-only.

---

## 4. Maintain Quest-Agnostic Design

1. **No Hardcoded Puzzle Tips**
   - Remove or omit any references to known puzzle solutions (such as 1,2,5,10 specifics).
   - Ensure all puzzle data is derived from the quest’s observation text.

2. **Clean Prompt**
   - Make sure each prompt only includes the scenario, constraints, and the chain-of-thought instruction.
   - Use a fully generic approach to boat or any other puzzle.

---

## 5. Tune & Verify with Sonnet-3.5

1. **Test Temperature & Token Limits**
   - Provide stable defaults (e.g., temperature ~0.7) for puzzle tasks.
   - Increase `max_tokens` if the quest text is large.

2. **Encourage Claude-Style Clarity**
   - Inline short instructions: “Please break down constraints step by step; then give your final numeric decision in JSON.”

3. **Measure Results**
   - After the chain-of-thought is implemented, re-run the boat quest and other short quests.
   - Document success rates.

---

## 6. Deliverable Summary

- **Refactor**: Create or modify `reasoning.jinja` with chain-of-thought instructions.
- **Agent Config**: `use_advanced_reasoning` plus fallback to simpler approach.
- **Logging**: Capture `reasoning` text in debug mode, store numeric `action` for environment.
- **Quest Agnostic**: No puzzle-specific solutions or hints.
- **Completed**: Once the agent can reliably solve boat and similarly structured quests with a chain-of-thought approach.
