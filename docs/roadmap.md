# LLM Quest Benchmark Roadmap

## Core Concept
Enhance **LLM Quest Benchmark** to support advanced agents with memory and a basic tool, using cloud LLMs (Claude, OpenAI, Google), keeping it simple for solo architect (me) and Claude (Sonnet 3.7) as programmer.

## Implementation Details

### Agent Storage
- **Format**: JSON files in `agents/` (e.g., `agents/agent_id.json`)
- **Schema**:
  - `agent_id`: "advanced-agent"
  - `model`: "claude-3-sonnet" (supports Claude/OpenAI/Google)
  - `temperature`: 0.7
  - `system_template`: "You are an adventurer in a text-based quest."
  - `action_template`: "Based on state: {{state}}, I will {{action}}"
  - `memory`:
    - `type`: "message_history" | "summary" (raw history or summarized)
    - `max_history`: 10 (adjustable, 10+)
  - `tools`: ["calculator"] (single tool for simplicity)

### CLI Commands
- **Existing**:
  - `llm-quest agents list`
  - `llm-quest agents show <agent_id>`
  - `llm-quest agents new [--yaml config.yaml]`
  - `llm-quest agents edit <agent_id>`
  - `llm-quest agents delete <agent_id>`
- **New**:
  - `llm-quest agents set-memory <agent_id> <type> <max_history>`: Set memory type and size (e.g., "summary 10")
  - `llm-quest agents add-tool <agent_id> calculator`: Add calculator tool
  - `llm-quest agents remove-tool <agent_id> calculator`: Remove calculator tool

### Web Interface
- **Updates**:
  - Add memory type dropdown ("message_history", "summary") and `max_history` field (default: 10)
  - Add calculator tool checkbox

### Code Refactoring
- **Runner**:
  - Pass memory (raw history or summary) to agent input
  - Handle calculator tool with mock response (e.g., "Result: 42")
- **Summarizer**:
  - If `memory.type = "summary"`, use a cloud LLM to generate a concise summary of last 10+ states/actions

### Quest Environment
- Include memory (history or summary) in agent input
- Support calculator tool call with predefined response

### Evaluation Metrics
- Log to text file: Quest Completion Rate (Yes/No), Steps Taken

## Phases
1. **Phase 1: Memory Support**
   - Add `memory` to schema (`type`, `max_history`)
   - Update runner to pass raw history (default: `message_history`, 10 entries)
   - Add CLI/UI options for memory settings

2. **Phase 2: Summarizer**
   - Implement summarizer option using a cloud LLM (e.g., Claude)
   - Update runner to use summary if `type = "summary"`

3. **Phase 3: Tool Integration**
   - Add `tools` field with calculator
   - Implement basic calculator handling in environment
   - Update CLI/UI to toggle calculator

4. **Phase 4: Metrics**
   - Log completion rate and steps taken
   - Write script to summarize results

5. **Phase 5: Testing & Docs**
   - Test with a quest using memory and calculator
   - Update README with new features

## Next Steps
- **Start Phase 1**: Add memory to schema and runner (raw history, max 10). Claude generates code; you review/test.
- **Test Memory**: Run a sample quest needing history (e.g., recall a clue). Adjust based on results.
- **Add Summarizer**: Implement Phase 2 with Claude summarizing 10+ states/actions. Test both history and summary modes.
- **Integrate Tool**: Add calculator in Phase 3. Test with a quest requiring a calculation (e.g., "Add 5 and 3").
- **Log Metrics**: Implement Phase 4 logging. Compare runs with/without memory/tools.
- **Finalize**: Test all features in Phase 5, update README, and refine as needed.