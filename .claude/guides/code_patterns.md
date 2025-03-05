# Common Code Patterns

## Agent Configuration

```python
from llm_quest_benchmark.schemas.agent import AgentConfig, MemoryConfig

# Create agent with memory
agent_config = AgentConfig(
    agent_id="memory-agent",
    model="claude-3-5-sonnet-latest",
    temperature=0.7,
    system_template="You are a player in a text adventure game.",
    action_template="Make a decision based on the state.",
    memory=MemoryConfig(
        type="message_history",
        max_history=10
    ),
    tools=["calculator"]
)
```

## Memory Usage

```python
# Access memory in prompt renderer
memory_context = renderer._get_memory_context()
if memory_type == "message_history":
    return {
        "memory": recent_history
    }
elif memory_type == "summary":
    summary = self._generate_history_summary(recent_history)
    return {
        "memory": summary
    }
```

## Tool Implementation

```python
# Calculator tool handling
def handle_calculator_tool(request: str) -> str:
    """Handle calculator tool request"""
    try:
        # Clean up request
        clean_request = re.sub(r'calculate\s+', '', request.lower())

        # Evaluate the expression
        result = eval(clean_request, {"__builtins__": {}}, {})
        return f"Calculator result: {result}"
    except Exception as e:
        return f"Calculator error: {str(e)}"
```

## Database Operations

```python
# Backup and restore database
def export_runs_to_file(app):
    """Export runs to backup file"""
    try:
        with app.app_context():
            runs = Run.query.all()
            if not runs:
                return

            # Convert to JSON and save
            run_data = [run.to_dict() for run in runs]
            with open(backup_file, 'w') as f:
                json.dump(run_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error exporting runs: {e}")
```

## Flask Web Interface

```python
# Flask route definition
@bp.route('/analyze/run/<int:run_id>')
def run_details(run_id):
    """Show details for a specific run"""
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()

    # Calculate statistics
    total_steps = len(steps)
    decision_points = sum(1 for step in steps if step.choices and len(step.choices) > 1)

    return render_template('analyze/run_details.html',
                          run=run,
                          steps=steps,
                          total_steps=total_steps,
                          decision_points=decision_points)
```
