"""Quest and engine provenance used to gate replay and resume."""

from __future__ import annotations

import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = REPO_ROOT / "space-rangers-quest"
ENGINE_SOURCES = (
    ENGINE_ROOT / "src/lib/qmreader.ts",
    ENGINE_ROOT / "src/lib/qmplayer/index.ts",
    ENGINE_ROOT / "src/lib/qmplayer/funcs.ts",
)


def quest_checksum(quest_file: str | Path) -> str:
    """SHA-256 of the quest file bytes, used to detect quest mutation."""
    path = Path(quest_file)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


@lru_cache(maxsize=1)
def engine_revision() -> str:
    """Identify the TypeScript engine build backing this run.

    Prefers the submodule commit; falls back to a digest of the engine sources
    so a dirty or detached checkout still produces a stable identifier.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(ENGINE_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        revision = proc.stdout.strip()
        if revision:
            return f"git:{revision}"
    except (subprocess.SubprocessError, OSError):
        pass

    hasher = hashlib.sha256()
    for source in ENGINE_SOURCES:
        if source.exists():
            hasher.update(source.read_bytes())
    return f"src:{hasher.hexdigest()[:16]}"
