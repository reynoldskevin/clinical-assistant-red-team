"""SQLite exploit store + event log + migrations (ticket 004).

Stdlib-only persistence layer. A migration-aware SQLite store with a fixed set
of native columns for indexed/queried fields, plus a JSON ``data`` TEXT column
for arbitrary extra keys.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field


@dataclass
class Migration:
    """A single migration step: a name and the SQL statements to run."""

    name: str
    statements: list[str] = field(default_factory=list)


_BASELINE = [
    Migration(
        name="0001_baseline",
        statements=[
            """
            CREATE TABLE IF NOT EXISTS attack_attempts (
                id INTEGER PRIMARY KEY,
                category TEXT,
                prompt TEXT,
                target_id TEXT,
                data TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY,
                severity TEXT,
                attack_category TEXT,
                target_version TEXT,
                status TEXT,
                data TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity)",
            "CREATE INDEX IF NOT EXISTS idx_findings_attack_category ON findings(attack_category)",
            "CREATE INDEX IF NOT EXISTS idx_findings_target_version ON findings(target_version)",
            """
            CREATE TABLE IF NOT EXISTS regression_cases (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT,
                data TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS coverage (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS cost (
                id INTEGER PRIMARY KEY,
                data TEXT
            )
            """,
        ],
    ),
]


class Store:
    """Migration-aware SQLite store for attempts, findings, and events."""

    def __init__(self, db_path, extra_migrations: list[Migration] | None = None):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Manual transaction control (autocommit-off/manual mode). With the legacy
        # sqlite3 module this lets an explicit BEGIN wrap DDL (ALTER/CREATE) so a
        # failed migration can be rolled back atomically. Every write method must
        # therefore commit its own changes explicitly.
        self.conn.isolation_level = None
        self._migrations = list(_BASELINE) + list(extra_migrations or [])
        self._apply_migrations()

    # ------------------------------------------------------------------ #
    # migrations
    # ------------------------------------------------------------------ #
    def _apply_migrations(self) -> None:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS migrations (name TEXT UNIQUE)"
        )
        applied = {
            r[0]
            for r in self.conn.execute("SELECT name FROM migrations").fetchall()
        }
        for migration in self._migrations:
            if migration.name in applied:
                continue
            # Explicit transaction so DDL (ALTER/CREATE) participates and a
            # partially-applied migration can be rolled back atomically.
            self.conn.execute("BEGIN")
            try:
                for stmt in migration.statements:
                    self.conn.execute(stmt)
                self.conn.execute(
                    "INSERT INTO migrations (name) VALUES (?)", (migration.name,)
                )
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                # Leave the DB unlocked so the caller can reopen it.
                self.conn.close()
                raise

    def schema_version(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM migrations").fetchone()
        return int(row[0])

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _split(data: dict, native_keys: set[str]) -> tuple[dict, dict]:
        native = {k: v for k, v in data.items() if k in native_keys}
        extra = {k: v for k, v in data.items() if k not in native_keys}
        return native, extra

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        blob = d.pop("data", None)
        if blob:
            extra = json.loads(blob)
            for k, v in extra.items():
                if k not in d or d[k] is None:
                    d[k] = v
        return d

    # ------------------------------------------------------------------ #
    # attack_attempts
    # ------------------------------------------------------------------ #
    def insert_attempt(self, data: dict) -> int:
        native, extra = self._split(data, {"category", "prompt", "target_id"})
        cur = self.conn.execute(
            "INSERT INTO attack_attempts (category, prompt, target_id, data) "
            "VALUES (?, ?, ?, ?)",
            (
                native.get("category"),
                native.get("prompt"),
                native.get("target_id"),
                json.dumps(extra),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_attempt(self, attempt_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM attack_attempts WHERE id=?", (attempt_id,)
        ).fetchone()
        return self._row_to_dict(row) if row is not None else None

    # ------------------------------------------------------------------ #
    # findings
    # ------------------------------------------------------------------ #
    _FINDING_NATIVE = {"severity", "attack_category", "target_version", "status"}

    def insert_finding(self, data: dict) -> int:
        native, extra = self._split(data, self._FINDING_NATIVE)
        cur = self.conn.execute(
            "INSERT INTO findings (severity, attack_category, target_version, status, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                native.get("severity"),
                native.get("attack_category"),
                native.get("target_version"),
                native.get("status"),
                json.dumps(extra),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_finding(self, finding_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, severity, attack_category, target_version, status, data "
            "FROM findings WHERE id=?",
            (finding_id,),
        ).fetchone()
        return self._row_to_dict(row) if row is not None else None

    def update_finding(self, finding_id: int, **fields) -> None:
        native, extra = self._split(fields, self._FINDING_NATIVE)
        if native:
            cols = ", ".join(f"{k}=?" for k in native)
            self.conn.execute(
                f"UPDATE findings SET {cols} WHERE id=?",
                (*native.values(), finding_id),
            )
        if extra:
            row = self.conn.execute(
                "SELECT data FROM findings WHERE id=?", (finding_id,)
            ).fetchone()
            current = json.loads(row["data"]) if row and row["data"] else {}
            current.update(extra)
            self.conn.execute(
                "UPDATE findings SET data=? WHERE id=?",
                (json.dumps(current), finding_id),
            )
        self.conn.commit()

    def list_findings(self, **filters) -> list[dict]:
        native, _ = self._split(filters, self._FINDING_NATIVE)
        sql = "SELECT id, severity, attack_category, target_version, status, data FROM findings"
        params: list = []
        if native:
            clauses = " AND ".join(f"{k}=?" for k in native)
            sql += " WHERE " + clauses
            params = list(native.values())
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # events
    # ------------------------------------------------------------------ #
    def append_event(self, data: dict) -> int:
        native, extra = self._split(data, {"kind"})
        cur = self.conn.execute(
            "INSERT INTO events (kind, data) VALUES (?, ?)",
            (native.get("kind"), json.dumps(extra)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_events(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, kind, data FROM events ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # cost
    # ------------------------------------------------------------------ #
    def insert_cost(self, data: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO cost (data) VALUES (?)", (json.dumps(data),)
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_costs(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, data FROM cost ORDER BY id ASC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        self.conn.close()
