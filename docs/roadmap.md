# LLM Quest Benchmark Roadmap

## Agent Management System Plan

### Core Concept
Replace model-centric design with agent-centric approach, allowing users to create, manage, edit, and reuse agent configurations.

### Implementation Details

#### 1. Agent Storage Format
- Store agents as JSON files in `agents/` directory
- Format: `agents/agent_id.json` 
- Schema:
```json
{
  "agent_id": "my-gpt4-agent",
  "model": "gpt-4o",
  "temperature": 0.7,
  "system_template": "full template text here...",
  "action_template": "full template text here..."
}
```

#### 2. CLI Commands
- `llm-quest agents list`: List all available agents
- `llm-quest agents show <agent_id>`: Show details for specific agent
- `llm-quest agents new [--yaml config.yaml]`: Create new agent
- `llm-quest agents edit <agent_id>`: Edit existing agent
- `llm-quest agents delete <agent_id>`: Delete agent

#### 3. Web Interface
- New "Agents" tab in navigation menu
- Main view: List of all agents with edit/delete buttons
- Detail view: Edit form with template editors
- Components:
  - Text inputs for agent_id, model, temperature
  - Monaco/CodeMirror editors for system_template and action_template
  - Save/Cancel buttons
  - Preview button to see formatted templates

#### 4. Database Changes
- Modify existing schemas to reference agent_id consistently
- Update analysis queries to group by agent_id instead of model
- Ensure benchmark results properly track agent_id

#### 5. Code Refactoring
- Update benchmark runner to use agent_id as primary identifier
- Modify analysis views to compare agents instead of models
- Ensure benchmark config uses agents list instead of model list

#### 6. Template Management
- Provide template preview functionality
- Add syntax highlighting for Jinja templates
- Include variable substitution testing

### Implementation Phases

1. **Storage & Schema**: Create agent storage system and JSON schema
2. **CLI Commands**: Implement basic agent management commands
3. **Agent Usage**: Update benchmark/quest runner to use agents
4. **Web UI**: Create agent management pages
5. **Analysis**: Update analysis views to use agent_id consistently