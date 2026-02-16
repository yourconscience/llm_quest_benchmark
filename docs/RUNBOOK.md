# Runbook

## Setup
```bash
git submodule update --init --recursive
uv sync --extra dev
npm install
cd space-rangers-quest
npm install --legacy-peer-deps
npm run build
cd ..
cp .env.template .env
```

For Node 23+:
```bash
export NODE_OPTIONS=--openssl-legacy-provider
```

## Smoke Checks
```bash
uv run python -m pytest --version
uv run llm-quest --help
NODE_OPTIONS=--openssl-legacy-provider node -r ts-node/register llm_quest_benchmark/executors/ts_bridge/consoleplayer.ts quests/Boat.qm --parse
NODE_OPTIONS=--openssl-legacy-provider uv run llm-quest run --quest quests/Boat.qm --model random_choice --timeout 20 --debug
```

## Run Services

### Flask UI
```bash
uv run llm-quest server
```
Open `http://localhost:8000`.

## Agent Experiment Workflow
1. Choose quest(s) from registry-backed paths.
2. Choose model + prompt template + temperature.
3. Run via:
   - Flask monitor UI, or
   - CLI `run`/`benchmark`.
4. Review:
   - UI analyze tab, and/or
   - CLI `analyze` output.

## Useful CLI Commands
```bash
# single run
uv run llm-quest run --quest quests/Boat.qm --model gpt-5-mini --timeout 60 --debug

# benchmark config run
uv run llm-quest benchmark --config configs/benchmarks/provider_suite_v1.yaml
uv run llm-quest benchmark --config configs/benchmarks/provider_suite_v2.yaml

# benchmark markdown report
uv run llm-quest benchmark-report --benchmark-id <BENCHMARK_ID>

# run-summary decision trace analyzer
uv run llm-quest analyze-run --agent llm_gpt-5-mini --quest Diehard

# inspect latest run
uv run llm-quest analyze --last

# docs drift scan (doc-gardening)
./scripts/doc_gardening.sh
```

## Artifacts Layout
- Benchmark-level artifacts:
  - `results/benchmarks/<benchmark_id>/benchmark_config.json`
  - `results/benchmarks/<benchmark_id>/benchmark_summary.json`
- Run-level artifacts:
  - `results/<agent_id>/<quest_name>/run_<run_id>/run_summary.json`

## Troubleshooting

### Bridge startup fails
Ensure the submodule exists and is built:
```bash
git submodule update --init --recursive
cd space-rangers-quest && npm install --legacy-peer-deps && npm run build
```

### OpenSSL / webpack-style crypto errors on new Node
```bash
export NODE_OPTIONS=--openssl-legacy-provider
```

### Invalid model or missing API key
- Confirm model appears in Flask dropdown / `MODEL_CHOICES`.
- Check `.env` and key names:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_API_KEY`
  - `DEEPSEEK_API_KEY`
- Note: `gpt-5-mini` currently uses provider-default temperature (custom value is ignored).

### Database issues
Remove stale local DBs only when you want a clean slate:
```bash
rm -f metrics.db instance/llm_quest.sqlite
```
