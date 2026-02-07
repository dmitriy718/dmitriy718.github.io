from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class IncidentRecord:
    id: int
    service: str
    check_name: str
    status: str
    message: str
    created_at: str
    resolved_at: Optional[str]


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
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
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT,
                    check_name TEXT,
                    status TEXT,
                    message TEXT,
                    created_at TEXT,
                    resolved_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER,
                    action TEXT,
                    status TEXT,
                    details TEXT,
                    created_at TEXT
                )
                """
            )

    def record_incident(
        self, service: str, check_name: str, status: str, message: str
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO incidents (service, check_name, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (service, check_name, status, message, now),
            )
            return int(cursor.lastrowid)

    def resolve_incident(self, incident_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE incidents SET resolved_at = ? WHERE id = ?",
                (now, incident_id),
            )

    def record_action(
        self, incident_id: int, action: str, status: str, details: str
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO actions (incident_id, action, status, details, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (incident_id, action, status, details, now),
            )

    def recent_incidents(self, limit: int = 10) -> List[IncidentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            IncidentRecord(
                id=row["id"],
                service=row["service"],
                check_name=row["check_name"],
                status=row["status"],
                message=row["message"],
                created_at=row["created_at"],
                resolved_at=row["resolved_at"],
            )
            for row in rows
        ]
