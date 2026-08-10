"""Persist trigger history and dedupe keys."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def install_root():
    return Path('/data/support')


def default_state_path() -> Path:
    return install_root() / "data" / "alarm_monitor.db"


@dataclass
class TriggerRecord:
    id: int
    alarm_id: str
    alarm_namespace: str
    workflow: str
    workflow_definition: str
    success: bool
    transaction_id: str | None
    error: str | None
    triggered_at: float
    alarm_snapshot: dict[str, Any]


class TriggerStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or default_state_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trigger_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedupe_key TEXT NOT NULL,
                    alarm_id TEXT NOT NULL,
                    alarm_namespace TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    workflow_definition TEXT,
                    success INTEGER NOT NULL,
                    transaction_id TEXT,
                    error TEXT,
                    triggered_at REAL NOT NULL,
                    alarm_snapshot TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trigger_dedupe ON trigger_history(dedupe_key, triggered_at)"
            )
            conn.commit()

    @staticmethod
    def dedupe_key(alarm_id: str, workflow: str, namespace: str = "") -> str:
        return f"{namespace}|{alarm_id}|{workflow}".lower()

    def is_in_cooldown(
        self,
        alarm_id: str,
        workflow: str,
        *,
        namespace: str = "",
        cooldown_seconds: int = 300,
    ) -> bool:
        key = self.dedupe_key(alarm_id, workflow, namespace)
        cutoff = time.time() - cooldown_seconds
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT triggered_at FROM trigger_history
                WHERE dedupe_key = ? AND triggered_at >= ?
                ORDER BY triggered_at DESC LIMIT 1
                """,
                (key, cutoff),
            ).fetchone()
        return row is not None

    def record_trigger(
        self,
        *,
        alarm_id: str,
        workflow: str,
        namespace: str = "",
        workflow_definition: str = "",
        success: bool,
        transaction_id: str | None = None,
        error: str | None = None,
        alarm_snapshot: dict[str, Any] | None = None,
    ) -> int:
        import json

        key = self.dedupe_key(alarm_id, workflow, namespace)
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO trigger_history (
                    dedupe_key, alarm_id, alarm_namespace, workflow, workflow_definition,
                    success, transaction_id, error, triggered_at, alarm_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    alarm_id,
                    namespace,
                    workflow,
                    workflow_definition,
                    1 if success else 0,
                    transaction_id,
                    error,
                    now,
                    json.dumps(alarm_snapshot or {}),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def recent_triggers(self, limit: int = 50) -> list[dict[str, Any]]:
        import json

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM trigger_history
                ORDER BY triggered_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            snap = {}
            try:
                snap = json.loads(row["alarm_snapshot"] or "{}")
            except json.JSONDecodeError:
                snap = {}
            out.append(
                {
                    "id": row["id"],
                    "alarm_id": row["alarm_id"],
                    "namespace": row["alarm_namespace"],
                    "workflow": row["workflow"],
                    "workflow_definition": row["workflow_definition"],
                    "success": bool(row["success"]),
                    "transaction_id": row["transaction_id"],
                    "error": row["error"],
                    "triggered_at": row["triggered_at"],
                    "alarm": snap,
                }
            )
        return out

    def status_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM trigger_history").fetchone()[0]
            success = conn.execute(
                "SELECT COUNT(*) FROM trigger_history WHERE success = 1"
            ).fetchone()[0]
            failed = total - success
        return {
            "db_path": str(self.db_path),
            "total_triggers": total,
            "successful": success,
            "failed": failed,
        }
