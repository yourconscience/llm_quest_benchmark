# Paper Draft

This directory contains the repository-local LaTeX draft for the arXiv preprint.

## Scope

- The draft is intentionally conservative.
- It uses the six-model published leaderboard slice in `site/leaderboard.json` as the canonical public evidence base.
- The tier split comes from `configs/benchmarks/tiered/`.
- No new expensive benchmark matrices were run for this branch.

## Generate source data

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/build_paper_data.py
```

This writes CSV/JSON source data under `paper/data/` and TeX table fragments under `paper/tables/`.

## Build

Expected TeX toolchain:

```bash
latexmk -pdf -cd paper/main.tex
```

If `latexmk` is unavailable:

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Status and TODOs

- The draft text is complete enough for review, but it is still a preliminary preprint rather than a final camera-ready paper.
- The VPS used for this branch does not currently have `latexmk`, `pdflatex`, or `bibtex`, so TeX compilation was not verified here.
- The next substantive step is to run the balanced tiered reruns already defined in `configs/benchmarks/tiered/`.
