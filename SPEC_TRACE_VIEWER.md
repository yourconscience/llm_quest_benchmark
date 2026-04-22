# SPEC: Trace Viewer

## Goal

A lightweight, read-only trace inspector for LLM quest benchmark runs. View step-by-step agent decisions, reasoning, and outcomes without running the benchmark. Single static HTML file, deployable alongside the existing leaderboard on GitHub Pages.

## Non-goals

- Not a quest player or replay engine
- No backend, no server, no database access
- No editing or re-running traces
- Not a replacement for the leaderboard (complements it)

## User story / behavior

1. User opens `site/traces.html` in browser
2. Drags a `run_summary.json` file onto the page (or clicks to select)
3. Viewer shows:
   - **Header**: quest name, agent ID, outcome badge (SUCCESS/FAILURE/TIMEOUT), reward, duration, total steps, cost
   - **Step timeline**: vertical list of steps, each showing:
     - Step number + location_id
     - Observation text (the quest description the agent saw)
     - Available choices (numbered list)
     - LLM decision: chosen action highlighted, reasoning/analysis text if present, parse_mode indicator
     - Token usage per step (prompt + completion tokens)
     - Visual indicator for repeated actions (repetition detection)
   - **Summary sidebar**: total tokens, cost, repetition rate, exploration rate
4. Steps are collapsible (collapsed by default, showing just step number + chosen action + outcome indicator)
5. Click a step to expand full observation + reasoning
6. Color coding: green for steps leading to progress, red for repeated/loop steps
7. Supports both Russian and English quest text (UTF-8)

## Data format

Input: `run_summary.json` files as produced by the benchmark. Key fields:

```json
{
  "quest_name": "Boat",
  "agent_id": "llm_openrouter:google/gemini-3-flash-preview",
  "outcome": "SUCCESS",
  "reward": 10000.0,
  "run_duration": 45.2,
  "steps": [
    {
      "step": 1,
      "observation": "quest text...",
      "choices": {"1": "option A", "2": "option B"},
      "llm_decision": {
        "choice": {"1": "option A"},
        "reasoning": "I chose this because...",
        "analysis": "The situation requires...",
        "parse_mode": "json_parsed",
        "prompt_tokens": 450,
        "completion_tokens": 120
      }
    }
  ],
  "usage": {"prompt_tokens": 5000, "completion_tokens": 1200, "estimated_cost_usd": 0.003}
}
```

## Acceptance tests

1. Drop a run_summary.json, see all steps rendered correctly
2. Russian text displays without mojibake
3. Repetition loops visually obvious (highlighted red)
4. Works offline (no external API calls)
5. Page loads in <1s, handles traces with 400+ steps without lag
6. Mobile-responsive (readable on phone)

## Constraints

- Single HTML file with inline CSS/JS (like existing site pattern) or at most traces.html + traces.js
- Match existing site dark theme (var(--bg), var(--surface), etc.)
- Bootstrap 5.3.3 CDN (consistent with index.html and about.html)
- No build step, no npm, no framework
- File size under 30KB

## Future enhancements (out of scope for v1)

- Pre-built trace index: script exports all traces to a JSON bundle, viewer loads via URL params (enables shareable links)
- Side-by-side comparison of two runs on the same quest
- Integration with leaderboard: click a cell to view a trace
- Batch upload: drop a directory of traces, see aggregate stats
