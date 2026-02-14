# LLM Quest Benchmark

Benchmark how human and LLM agents solve Space Rangers text quests (`.qm`).

## What Works Now
- TypeScript quest engine bridge (`space-rangers-quest` + Python bridge wrapper)
- CLI run/play/analyze/benchmark flows
- Provider-aware LLM clients:
  - OpenAI
  - Anthropic
  - Google Gemini (via Google OpenAI-compatible endpoint)
  - OpenRouter (OpenAI-compatible)
  - DeepSeek (OpenAI-compatible)
- Flask UI (`llm-quest server`) with quest run + benchmark + analysis views

## Prerequisites
- Python 3.11+
- Node.js 18+ (Node 23+ requires `NODE_OPTIONS=--openssl-legacy-provider`)
- `uv`

## Setup
```bash
git clone --recursive <your-fork-url>
cd llm_quest_benchmark

git submodule update --init --recursive
uv sync --extra dev
npm install

cd space-rangers-quest
npm install --legacy-peer-deps
npm run build
cd ..
```

Create environment file:
```bash
cp .env.template .env
```

For Node 23+:
```bash
export NODE_OPTIONS=--openssl-legacy-provider
```

## CLI Usage
```bash
uv run llm-quest --help

# Random smoke run
NODE_OPTIONS=--openssl-legacy-provider uv run llm-quest run --quest quests/Boat.qm --model random_choice --timeout 20 --debug

# Interactive play
uv run llm-quest play --quest quests/Boat.qm

# Analyze latest run
uv run llm-quest analyze --last

# Benchmark matrix from YAML
uv run llm-quest benchmark --config configs/test/test_benchmark.yaml
```

## Web Usage

```bash
uv run llm-quest server
```
Open: `http://localhost:8000`

## Tests
```bash
uv run python -m pytest
```

## Key Paths
- `AGENTS.md` - repo guide
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/DEPLOYMENT.md`
- `docs/RUNBOOK.md`
- `docs/PLANS.md`

## Notes
- Quest engine submodule is required.
- API-key dependent model execution needs provider env vars:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_API_KEY`
  - `OPENROUTER_API_KEY`
  - `DEEPSEEK_API_KEY`
- Benchmark artifacts are written to:
  - `results/benchmarks/<benchmark_id>/benchmark_config.json`
  - `results/benchmarks/<benchmark_id>/benchmark_summary.json`
- Per-run step logs remain in:
  - `results/<agent_id>/<quest_name>/run_<run_id>/`
