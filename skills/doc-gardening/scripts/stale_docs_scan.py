#!/usr/bin/env python3
"""Scan markdown docs for stale references and report likely drift."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List


DOC_PATHS = ("README.md", "AGENTS.md")
DOC_DIR_GLOB = "docs/**/*.md"

STALE_TERMS = {
    "ngrok-free.app": "Legacy hosted demo URL; verify current deployment path.",
    "quests/kr1/Boat.qm": "Stale quest path; default quest moved.",
    "Streamlit": "Legacy UI direction; project now uses Flask web app.",
    "LiteLLM": "Client stack no longer uses LiteLLM in current code.",
    "FastAPI backend": "Project now uses Flask web interface.",
    "Next.js frontend": "Project no longer ships the Next.js UI in this repo.",
    "llm-quest api-server": "Removed command; use `llm-quest server`.",
    "llm_quest_benchmark/web_next": "Removed path; Flask UI is canonical.",
}

KNOWN_CLI_COMMANDS = {
    "run",
    "play",
    "analyze",
    "analyze-run",
    "cleanup",
    "benchmark",
    "benchmark-report",
    "server",
}

PATH_REF_RE = re.compile(r"`([^`\n]+)`")
CLI_RE = re.compile(r"\bllm-quest\s+([a-z][a-z0-9-]*)\b")
PATH_PREFIXES = (
    "llm_quest_benchmark/",
    "docs/",
    "skills/",
    "configs/",
    "quests/",
    "scripts/",
    "space-rangers-quest/",
)
PATH_SUFFIXES = (
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".sh",
    ".sql",
)


@dataclass
class Finding:
    severity: str
    file: str
    line: int
    category: str
    message: str
    snippet: str


def iter_doc_files(root: Path) -> Iterable[Path]:
    for rel in DOC_PATHS:
        p = root / rel
        if p.exists():
            yield p
    for p in root.glob(DOC_DIR_GLOB):
        if p.is_file():
            yield p


def looks_like_path(token: str) -> bool:
    if "<" in token or ">" in token:
        return False
    if token.startswith(("http://", "https://")):
        return False
    if token.startswith(("$", "--", "-")):
        return False
    if token.startswith("text/"):
        return False
    if " " in token:
        return False
    if token.startswith(PATH_PREFIXES):
        return True
    if token.startswith(("./", "../", "/")) and token.endswith(PATH_SUFFIXES):
        return True
    if "/" in token and token.endswith(PATH_SUFFIXES):
        return True
    return False


def resolve_path(root: Path, token: str) -> bool:
    candidates = [
        root / token,
        root / "llm_quest_benchmark" / token,
    ]
    return any(p.exists() for p in candidates)


def scan_file(root: Path, file_path: Path) -> List[Finding]:
    findings: List[Finding] = []
    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for idx, line in enumerate(lines, start=1):
        for term, hint in STALE_TERMS.items():
            if term in line:
                findings.append(
                    Finding(
                        severity="medium",
                        file=str(file_path.relative_to(root)),
                        line=idx,
                        category="stale-term",
                        message=f"Found potentially stale term '{term}'. {hint}",
                        snippet=line.strip(),
                    )
                )

        for match in CLI_RE.finditer(line):
            cmd = match.group(1)
            if cmd not in KNOWN_CLI_COMMANDS:
                findings.append(
                    Finding(
                        severity="high",
                        file=str(file_path.relative_to(root)),
                        line=idx,
                        category="unknown-cli-command",
                        message=f"Unknown documented llm-quest command: '{cmd}'.",
                        snippet=line.strip(),
                    )
                )

        for match in PATH_REF_RE.finditer(line):
            token = match.group(1)
            if looks_like_path(token) and not resolve_path(root, token):
                findings.append(
                    Finding(
                        severity="high",
                        file=str(file_path.relative_to(root)),
                        line=idx,
                        category="missing-path-ref",
                        message=f"Backticked path does not exist: '{token}'.",
                        snippet=line.strip(),
                    )
                )

    return findings


def format_markdown(findings: List[Finding]) -> str:
    if not findings:
        return "No stale doc findings."
    output = ["# Doc Gardening Scan Report", "", f"Findings: {len(findings)}", ""]
    for f in findings:
        output.append(
            f"- [{f.severity}] `{f.file}:{f.line}` {f.category}: {f.message}\n"
            f"  - `{f.snippet}`"
        )
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: List[Finding] = []
    for doc in iter_doc_files(root):
        findings.extend(scan_file(root, doc))

    findings.sort(key=lambda x: (x.file, x.line, x.category))

    if args.format == "json":
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        print(format_markdown(findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
