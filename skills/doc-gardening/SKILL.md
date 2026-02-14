---
name: doc-gardening
description: Scan repository documentation for stale or obsolete content that diverges from current code behavior, then prepare focused documentation-only fix-up branches and open GitHub pull requests.
---

# Doc Gardening

Use this skill when documentation may be stale, contradictory, or no longer aligned with current code paths, commands, APIs, or architecture.

## Scope
- Markdown docs in:
  - `README.md`
  - `AGENTS.md`
  - `docs/**/*.md`

## Workflow

1. Run scanner:
```bash
uv run python skills/doc-gardening/scripts/stale_docs_scan.py --root . --format markdown
```

2. Triage findings:
- `high`: command/path/API definitely invalid now
- `medium`: likely stale wording or outdated architecture references
- `low`: style/clarity drift

3. Group changes into small doc-only PR slices:
- Example split:
  - PR 1: command/path fixes
  - PR 2: architecture/API alignment
  - PR 3: cleanup and consistency

4. For each slice:
- Create branch:
```bash
git checkout -b codex/docs-garden-<topic>
```
- Apply doc edits only.
- Validate:
```bash
uv run python skills/doc-gardening/scripts/stale_docs_scan.py --root . --format markdown
```

5. Commit and open PR:
```bash
git add README.md AGENTS.md docs
git commit -m "docs: align <topic> with current code behavior"
gh pr create \
  --title "docs: align <topic> with current behavior" \
  --body "This PR updates stale documentation detected by doc-gardening scan." \
  --base main
```

## Guardrails
- Keep PRs documentation-only unless the user explicitly asks for code fixes.
- Never invent commands or endpoints; confirm against code first.
- Prefer linking to source files when describing behavior.
- Keep behavior claims testable (include exact command where possible).

## Scanner Notes
- Scanner detects:
  - stale keywords (legacy infra references)
  - broken local path references in backticks
  - unknown `llm-quest` commands in docs
- Scanner output is advisory; human review decides final edits.
