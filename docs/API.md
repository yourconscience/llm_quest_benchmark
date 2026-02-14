# Flask Web Endpoints

This project uses Flask routes under three blueprints:
- `/monitor` for quest runs
- `/benchmark` for benchmark jobs
- `/analyze` for analytics and exports

## Monitor Endpoints

### `GET /monitor`
Render quest runner UI.

### `POST /monitor/init`
Initialize a run and return first state.

Request JSON:
```json
{
  "quest": "quests/Boat.qm",
  "model": "random_choice",
  "template": "reasoning",
  "temperature": 0.4,
  "timeout": 60
}
```

### `POST /monitor/run`
Run quest end-to-end (non-interactive) and persist run/steps.

### `POST /monitor/step/{run_id}`
Submit a manual step choice for an initialized run.

Request JSON:
```json
{
  "choice": 1
}
```

### `GET /monitor/runs`
List recent runs.

### `GET /monitor/runs/{run_id}`
Get run details plus step list.

### `GET /monitor/runs/{run_id}/readable`
Get human-readable plain-text run transcript.

### `GET /monitor/template/{template_name}`
Fetch prompt template source text.

## Benchmark Endpoints

### `GET /benchmark/`
Render benchmark UI.

### `POST /benchmark/run`
Start benchmark from YAML config.

Request JSON:
```json
{
  "config": "quests:\n  - quests/Boat.qm\nagents:\n  - model: random_choice\n"
}
```

### `GET /benchmark/status/{benchmark_id}`
Return benchmark progress/status.

### `GET /benchmark/results`
List recent benchmark runs and active jobs.

## Analyze Endpoints

### `GET /analyze/`
Render analysis dashboard.

### `GET /analyze/summary`
Return aggregate success/failure counts.

### `GET /analyze/model_comparison`
Return grouped quest/model performance.

### `GET /analyze/step_analysis`
Return location-level visit counts.

### `GET /analyze/run/{run_id}`
Render per-run analysis page.

### `GET /analyze/run/{run_id}/analysis`
Return JSON analysis for run.

### `GET /analyze/run/{run_id}/readable`
Return readable transcript for run.

### `GET /analyze/quest/{quest_name}`
Render quest-specific summary page.

### `GET /analyze/benchmark/{benchmark_id}`
Render benchmark analysis page.

### `GET /analyze/export`
Export analysis data.

### `POST /analyze/cleanup`
Clean old runs/benchmark rows based on request settings.
