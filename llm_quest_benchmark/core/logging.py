"""Unified logging and schema-v2 run persistence for LLM Quest Benchmark"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_quest_benchmark.schemas.records import (
    SCHEMA_VERSION,
    ProgressState,
    QuestSnapshot,
    QuestTransition,
    ResumeLineage,
    RunRecord,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Constants
#
# Both stores are process-wide defaults resolved from the environment at import
# time, so a benchmark worker started with ``spawn`` inherits the same isolated
# database and results tree as its parent instead of silently writing to the
# working directory.
DB_PATH_ENV_VAR = "LLM_QUEST_DB_PATH"
RESULTS_DIR_ENV_VAR = "LLM_QUEST_RESULTS_DIR"

DEFAULT_DB_PATH = os.environ.get(DB_PATH_ENV_VAR) or "metrics.db"
RESULTS_DIR = Path(os.environ.get(RESULTS_DIR_ENV_VAR) or "results")

LEGACY_DB_MESSAGE = (
    "metrics database uses the pre-v2 schema. Convert it with: "
    "llm-quest migrate-records --source <old.db> --output <new.db>"
)


def default_db_path() -> str:
    """Metrics database used whenever a caller supplies no explicit path.

    Resolved on every call so tests and tools can point the runtime at their own
    database without reaching into import-time defaults.
    """
    return DEFAULT_DB_PATH

RUNS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schema_version INTEGER NOT NULL,
        quest_file TEXT NOT NULL,
        quest_name TEXT NOT NULL,
        quest_checksum TEXT NOT NULL,
        quest_language TEXT NOT NULL,
        engine_revision TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        treatment TEXT NOT NULL,
        treatment_signature TEXT NOT NULL,
        benchmark_id TEXT,
        lineage TEXT,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        run_duration REAL,
        outcome TEXT,
        reward REAL,
        usage TEXT,
        transcript_diagnostics TEXT,
        progress TEXT,
        terminal_snapshot TEXT
    )
"""

TRANSITIONS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        transition_index INTEGER NOT NULL,
        before_state TEXT NOT NULL,
        action TEXT NOT NULL,
        after_state TEXT NOT NULL,
        response TEXT,
        usage TEXT,
        progress TEXT,
        provenance TEXT NOT NULL,
        replay_status TEXT NOT NULL,
        reasoning_mode TEXT,
        FOREIGN KEY (run_id) REFERENCES runs (id)
    )
"""

# SQLite stores the same logical record as run_summary.json, flattened: each
# column is one field of a canonical domain.
RUN_COLUMNS = (
    "id",
    "schema_version",
    "quest_file",
    "quest_name",
    "quest_checksum",
    "quest_language",
    "engine_revision",
    "agent_id",
    "treatment",
    "treatment_signature",
    "benchmark_id",
    "lineage",
    "start_time",
    "end_time",
    "run_duration",
    "outcome",
    "reward",
    "usage",
    "transcript_diagnostics",
    "progress",
    "terminal_snapshot",
)


class LogManager:
    """Manages logging configuration"""

    def __init__(self, name: str = "llm_quest"):
        self.logger = logging.getLogger("llm_quest" if name == "llm_quest" else f"llm_quest.{name}")

    def setup(self, debug: bool = False):
        """Setup logging configuration"""
        level = logging.DEBUG if debug else logging.INFO
        self.logger.setLevel(level)

        # Configure other loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    def get_logger(self):
        """Get the logger"""
        return self.logger


def verify_v2_schema(conn: sqlite3.Connection) -> bool:
    """Return whether a v2 ``runs`` table exists, refusing a legacy database.

    A database with no ``runs`` table is simply empty, not legacy; readers use
    that to distinguish "nothing recorded yet" from "needs migration".
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    if cursor.fetchone() is None:
        return False

    cursor.execute("PRAGMA table_info(runs)")
    columns = {row[1] for row in cursor.fetchall()}
    if "schema_version" not in columns:
        raise RuntimeError(LEGACY_DB_MESSAGE)
    return True


def ensure_v2_schema(conn: sqlite3.Connection) -> None:
    """Create the v2 tables, refusing to touch a legacy database.

    There is no in-place upgrade path: legacy databases are converted once by
    ``llm-quest migrate-records`` into a fresh v2 destination.
    """
    verify_v2_schema(conn)
    cursor = conn.cursor()
    cursor.execute(RUNS_TABLE_SQL)
    cursor.execute(TRANSITIONS_TABLE_SQL)
    conn.commit()


class QuestLogger:
    """Persists schema-v2 runs to SQLite and exports one run_summary.json.

    Run identity, quest provenance, and the harness treatment are written
    before the first transition, so nothing is patched into the record after
    the JSON export.
    """

    DEFAULT_REPETITION_WINDOW = 5

    # Thread-local storage for database connections
    _local = threading.local()
    # Track all instances for cleanup
    _instances = []

    def __init__(self, db_path: str | None = None, debug: bool = False, agent: str | None = None):
        """Initialize the quest logger.

        Args:
            db_path: Path to SQLite database; defaults to DEFAULT_DB_PATH at call time
            debug: Enable debug logging
            agent: Agent identifier used for the results directory
        """
        self.db_path = db_path or default_db_path()
        self.debug = debug
        self.agent = agent
        self._repetition_window = self.DEFAULT_REPETITION_WINDOW
        self.current_run_id = None
        self.record: RunRecord | None = None
        self.start_time: datetime | None = None
        self._finalize_lock = threading.Lock()
        self._finalized = False

        # Setup logger
        self.logger = logging.getLogger("quest_logger")
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

        # Initialize connection for this thread
        self._init_connection()

        # Add this instance to the list of all instances
        QuestLogger._instances.append(self)

        # Setup exit handler if this is the first instance
        if len(QuestLogger._instances) == 1:
            import atexit
            import signal

            is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))

            # Define shutdown handler
            def _shutdown_handler(signal=None, frame=None):
                self.logger.info("Shutting down gracefully - closing database connections")
                for instance in QuestLogger._instances:
                    instance.close()
                QuestLogger._instances.clear()

            if not is_pytest:
                # Register shutdown handlers
                atexit.register(_shutdown_handler)

                # Only register signal handlers in the main thread
                if threading.current_thread() is threading.main_thread():
                    try:
                        signal.signal(signal.SIGINT, _shutdown_handler)
                        signal.signal(signal.SIGTERM, _shutdown_handler)
                    except ValueError:
                        # Signal handlers can only be set in the main thread
                        self.logger.debug("Skipping signal handlers in non-main thread")

    def _init_connection(self):
        """Initialize a thread-local database connection.

        The connection cache is keyed by database path: two loggers in the same
        thread pointing at different databases must never share a handle.
        """
        conn = getattr(self._local, "conn", None)
        if conn is not None and getattr(self._local, "db_path", None) != self.db_path:
            conn.close()
            conn = None
            self._local.conn = None
            self._local.cursor = None

        if conn is None:
            connection = sqlite3.connect(self.db_path)
            try:
                ensure_v2_schema(connection)
            except Exception:
                connection.close()
                raise
            self._local.conn = connection
            self._local.cursor = connection.cursor()
            self._local.db_path = self.db_path

    def start_run(
        self,
        *,
        quest_file: str,
        quest_name: str,
        quest_checksum: str,
        quest_language: str,
        engine_revision: str,
        agent_id: str,
        treatment: dict[str, Any],
        benchmark_id: str | None = None,
        lineage: ResumeLineage | None = None,
    ) -> int:
        """Create the run row with complete metadata and return its id."""
        self._init_connection()

        self.agent = agent_id
        self.start_time = datetime.utcnow()
        self._finalized = False

        self._local.cursor.execute(
            """
            INSERT INTO runs (
                schema_version, quest_file, quest_name, quest_checksum, quest_language,
                engine_revision, agent_id, treatment, treatment_signature, benchmark_id,
                lineage, start_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                SCHEMA_VERSION,
                quest_file,
                quest_name,
                quest_checksum,
                quest_language,
                engine_revision,
                agent_id,
                json.dumps(treatment, ensure_ascii=False),
                str(treatment.get("signature") or ""),
                benchmark_id,
                json.dumps(lineage.to_dict(), ensure_ascii=False) if lineage else None,
                self.start_time,
            ),
        )
        self._local.conn.commit()
        self.current_run_id = self._local.cursor.lastrowid

        self.record = RunRecord(
            run_id=self.current_run_id,
            quest_file=quest_file,
            quest_name=quest_name,
            quest_checksum=quest_checksum,
            quest_language=quest_language,
            engine_revision=engine_revision,
            agent_id=agent_id,
            treatment=treatment,
            started_at=self.start_time.isoformat(),
            benchmark_id=benchmark_id,
            lineage=lineage,
        )
        return self.current_run_id

    def log_transition(self, transition: QuestTransition) -> None:
        """Persist one executed transition."""
        if self.record is None or self.current_run_id is None:
            self.logger.warning("Cannot log transition, no active run")
            return

        self._init_connection()
        self.record.transitions.append(transition)

        if self.debug:
            self.logger.debug(self.format_transition_for_console(transition))

        try:
            payload = transition.to_dict()
            self._local.cursor.execute(
                """
                INSERT INTO transitions (
                    run_id, transition_index, before_state, action, after_state,
                    response, usage, progress, provenance, replay_status, reasoning_mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.current_run_id,
                    transition.index,
                    json.dumps(payload["before"], ensure_ascii=False),
                    json.dumps(payload["action"], ensure_ascii=False),
                    json.dumps(payload["after"], ensure_ascii=False),
                    json.dumps(payload["response"], ensure_ascii=False) if payload["response"] else None,
                    json.dumps(payload["usage"], ensure_ascii=False),
                    json.dumps(payload["progress"], ensure_ascii=False),
                    transition.provenance,
                    transition.replay_status,
                    transition.reasoning_mode,
                ),
            )
            self._local.conn.commit()
        except Exception as e:
            self.logger.error(f"Error logging transition: {e}")

    def adopt_transitions(self, transitions: list[QuestTransition]) -> None:
        """Persist prior transitions carried over into a resumed run."""
        for transition in transitions:
            self.log_transition(transition)

    def finish_run(
        self,
        outcome: str,
        reward: float = 0.0,
        terminal_snapshot: QuestSnapshot | None = None,
        progress: ProgressState | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        """Record the terminal outcome and export the v2 run summary.

        First write wins: late outcome updates from a background timeout race
        cannot overwrite the outcome already recorded for this run.
        """
        with self._finalize_lock:
            if self.record is None or not self.current_run_id:
                self.logger.warning("Cannot set outcome, no active run")
                return
            if self._finalized:
                self.logger.debug(
                    "Ignoring late outcome update for run %s: %s (already finalized as %s)",
                    self.current_run_id,
                    outcome,
                    self.record.outcome,
                )
                return

            end_time = datetime.utcnow()
            record = self.record
            record.outcome = outcome
            record.reward = reward
            record.terminal_snapshot = terminal_snapshot
            record.ended_at = end_time.isoformat()
            record.run_duration = (end_time - self.start_time).total_seconds() if self.start_time else None
            record.usage = self.aggregate_usage(record.transitions)
            record.transcript_diagnostics = self.calculate_metrics(
                record.transitions, outcome, self._repetition_window
            )
            if diagnostics:
                record.transcript_diagnostics.update(diagnostics)
            if progress is not None:
                record.progress = progress

            try:
                self._local.cursor.execute(
                    """
                    UPDATE runs
                    SET end_time = ?, run_duration = ?, outcome = ?, reward = ?,
                        usage = ?, transcript_diagnostics = ?, progress = ?, terminal_snapshot = ?
                    WHERE id = ?
                    """,
                    (
                        end_time,
                        record.run_duration,
                        outcome,
                        reward,
                        json.dumps(record.usage, ensure_ascii=False),
                        json.dumps(record.transcript_diagnostics, ensure_ascii=False),
                        json.dumps(record.progress.to_dict(), ensure_ascii=False),
                        json.dumps(terminal_snapshot.to_dict(), ensure_ascii=False) if terminal_snapshot else None,
                        self.current_run_id,
                    ),
                )
                self._local.conn.commit()

                self._export_run_to_json()
                self._finalized = True
            except Exception as e:
                self.logger.error(f"Error setting quest outcome: {e}")

    @staticmethod
    def aggregate_usage(transitions: list[QuestTransition]) -> dict[str, Any]:
        """Sum token usage and cost across transitions."""
        prompt_tokens = completion_tokens = total_tokens = priced_steps = 0
        estimated_cost = 0.0
        for transition in transitions:
            usage = transition.usage or {}
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += int(usage.get("total_tokens") or (prompt + completion))
            if usage.get("estimated_cost_usd") is not None:
                estimated_cost += float(usage["estimated_cost_usd"])
                priced_steps += 1
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 8) if priced_steps > 0 else None,
            "priced_steps": priced_steps,
        }

    @staticmethod
    def calculate_metrics(
        transitions: list[QuestTransition],
        outcome: str | None,
        window: int = DEFAULT_REPETITION_WINDOW,
    ) -> dict[str, Any]:
        """Compute run-level behaviour metrics from canonical transitions."""
        recent_actions: list[int] = []
        repetition_count = 0
        choose_count = 0
        restore_count = 0
        default_decisions = 0
        reasoning_modes: dict[str, int] = {}

        for transition in transitions:
            if transition.reasoning_mode:
                reasoning_modes[transition.reasoning_mode] = reasoning_modes.get(transition.reasoning_mode, 0) + 1
            if transition.action.is_restore:
                restore_count += 1
                continue
            choose_count += 1
            if transition.response is not None and transition.response.is_default:
                default_decisions += 1
            index = transition.action.choice_index
            if index is None:
                continue
            if index in recent_actions:
                repetition_count += 1
            recent_actions.append(index)
            recent_actions = recent_actions[-window:]

        bad_decision_count = 1 if outcome == "FAILURE" and choose_count > 0 else 0
        return {
            "total_steps": choose_count,
            "total_transitions": len(transitions),
            "choose_transitions": choose_count,
            "restore_transitions": restore_count,
            "repetition_window": window,
            "repetition_count": repetition_count,
            "repetition_rate": (repetition_count / choose_count) if choose_count else 0.0,
            "bad_decision_count": bad_decision_count,
            "bad_decision_rate": (bad_decision_count / choose_count) if choose_count else 0.0,
            "default_decisions": default_decisions,
            "reasoning_modes": reasoning_modes,
        }

    def _export_run_to_json(self):
        """Export the complete run to a single run_summary.json file."""
        if self.record is None or not self.agent or not self.current_run_id:
            return

        try:
            run_dir = RESULTS_DIR / self.agent / self.record.quest_name / f"run_{self.current_run_id}"
            run_dir.mkdir(parents=True, exist_ok=True)

            run_summary_file = run_dir / "run_summary.json"
            with open(run_summary_file, "w", encoding="utf-8") as f:
                json.dump(self.record.to_dict(), f, indent=2, ensure_ascii=False)

            self.logger.debug(f"Exported run data to {run_summary_file}")
        except Exception as e:
            self.logger.error(f"Error exporting run to JSON: {e}")

    @staticmethod
    def format_transition_for_console(transition: QuestTransition) -> str:
        """Format a transition for console output."""
        choices_str = "\n".join(
            f"{i + 1}. {choice['text']}" for i, choice in enumerate(transition.before.choices)
        )
        if transition.action.is_restore:
            action_str = f"restore checkpoint {transition.action.checkpoint_index}"
        else:
            action_str = f"choose {transition.action.choice_index}"
        return (
            f"Transition {transition.index}:\n"
            f"Observation: {transition.before.observation}\n"
            f"Choices:\n{choices_str}\n"
            f"Action: {action_str}"
        )

    def close(self):
        """Close the database connection for this thread"""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
            self._local.cursor = None
            self._local.db_path = None
