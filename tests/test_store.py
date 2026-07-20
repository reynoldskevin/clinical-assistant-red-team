"""Acceptance tests for ticket 004 — SQLite exploit store + event log + migrations.

These tests are the FIXED contract for the persistence layer. They pin:
- `from forge.store import Store, Migration`
- `Store(db_path)` creates the schema from scratch (six tables) and records a schema_version.
- CRUD for `attack_attempts` and `findings`; ordered append to `events`.
- Indexes exist on findings.severity / findings.attack_category / findings.target_version.
- A `Migration` adds a column and PRESERVES existing rows; migrations are idempotent + versioned.

The store exposes its underlying `sqlite3.Connection` as `store.conn` for schema introspection.
`":memory:"` is accepted for ephemeral tests; a file path is used where reopen is required.
"""

import pytest


REQUIRED_TABLES = {
    "findings",
    "regression_cases",
    "attack_attempts",
    "events",
    "coverage",
    "cost",
}


def _finding(**over):
    data = {
        "severity": "high",
        "attack_category": "prompt_injection",
        "target_version": "v1",
        "description": "system prompt disclosure",
    }
    data.update(over)
    return data


def _table_names(store):
    rows = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def _indexed_columns(store, table):
    cols = set()
    for idx in store.conn.execute(f"PRAGMA index_list('{table}')").fetchall():
        idx_name = idx[1]
        for info in store.conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall():
            cols.add(info[2])
    return cols


def test_imports():
    from forge.store import Store, Migration  # noqa: F401


def test_schema_creates_and_records_version():
    from forge.store import Store

    s = Store(":memory:")
    assert isinstance(s.schema_version(), int)
    assert s.schema_version() >= 1


def test_all_six_tables_exist():
    from forge.store import Store

    s = Store(":memory:")
    assert REQUIRED_TABLES <= _table_names(s)


def test_attempt_crud():
    from forge.store import Store

    s = Store(":memory:")
    aid = s.insert_attempt(
        {"category": "prompt_injection", "prompt": "ignore instructions", "target_id": "copilot"}
    )
    assert isinstance(aid, int)
    got = s.get_attempt(aid)
    assert got["category"] == "prompt_injection"
    assert got["prompt"] == "ignore instructions"
    assert got["target_id"] == "copilot"


def test_finding_crud_and_update():
    from forge.store import Store

    s = Store(":memory:")
    fid = s.insert_finding(_finding(severity="critical"))
    assert isinstance(fid, int)

    got = s.get_finding(fid)
    assert got["severity"] == "critical"
    assert got["attack_category"] == "prompt_injection"

    # Update (the U in CRUD)
    s.update_finding(fid, severity="medium", status="resolved")
    got2 = s.get_finding(fid)
    assert got2["severity"] == "medium"
    assert got2["status"] == "resolved"


def test_list_findings_filters():
    from forge.store import Store

    s = Store(":memory:")
    s.insert_finding(_finding(severity="high", attack_category="prompt_injection"))
    s.insert_finding(_finding(severity="low", attack_category="data_exfiltration"))
    s.insert_finding(_finding(severity="high", attack_category="data_exfiltration"))

    highs = s.list_findings(severity="high")
    assert len(highs) == 2
    assert all(f["severity"] == "high" for f in highs)

    exfil = s.list_findings(attack_category="data_exfiltration")
    assert len(exfil) == 2
    assert all(f["attack_category"] == "data_exfiltration" for f in exfil)


def test_events_appended_in_order():
    from forge.store import Store

    s = Store(":memory:")
    kinds = ["run_started", "directive_selected", "attempt_made", "verdict", "run_finished"]
    ids = [s.append_event({"kind": k, "actor": "orchestrator"}) for k in kinds]

    # ids are strictly increasing (monotonic append)
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)

    events = s.get_events()
    assert [e["kind"] for e in events] == kinds


def test_indexes_on_the_three_keys():
    from forge.store import Store

    s = Store(":memory:")
    indexed = _indexed_columns(s, "findings")
    assert {"severity", "attack_category", "target_version"} <= indexed


def test_migration_adds_field_and_preserves_rows(tmp_path):
    from forge.store import Store, Migration

    path = str(tmp_path / "forge.db")
    s = Store(path)
    base = s.schema_version()
    fid = s.insert_finding(_finding(description="preserve me"))
    s.close()

    migration = Migration(
        name="0002_add_notes",
        statements=["ALTER TABLE findings ADD COLUMN notes TEXT"],
    )
    s2 = Store(path, extra_migrations=[migration])

    # version advanced by exactly one
    assert s2.schema_version() == base + 1
    # the pre-existing row survived with its data intact
    got = s2.get_finding(fid)
    assert got is not None
    assert got["description"] == "preserve me"
    assert got["severity"] == "high"
    # the new column exists and defaults to NULL for the old row
    row = s2.conn.execute("SELECT notes FROM findings WHERE id=?", (fid,)).fetchone()
    assert row[0] is None
    s2.close()


def test_migrations_are_idempotent(tmp_path):
    from forge.store import Store, Migration

    path = str(tmp_path / "forge.db")
    migration = Migration(
        name="0002_add_notes",
        statements=["ALTER TABLE findings ADD COLUMN notes TEXT"],
    )

    s1 = Store(path, extra_migrations=[migration])
    v1 = s1.schema_version()
    s1.close()

    # reopening with the same migration must NOT re-apply it (no error, version stable)
    s2 = Store(path, extra_migrations=[migration])
    assert s2.schema_version() == v1
    s2.close()


def test_failed_migration_rolls_back_atomically(tmp_path):
    """A multi-statement migration that fails partway must leave NO partial schema
    change and must NOT be recorded — otherwise the store becomes un-reopenable
    (the failed DDL re-runs and throws 'duplicate column'). Migrations must be atomic.
    """
    from forge.store import Store, Migration

    path = str(tmp_path / "forge.db")
    Store(path).close()  # establish baseline

    bad = Migration(
        name="0002_bad",
        statements=[
            "ALTER TABLE findings ADD COLUMN notes TEXT",       # would succeed alone
            "ALTER TABLE does_not_exist ADD COLUMN x TEXT",      # fails → whole migration must roll back
        ],
    )
    with pytest.raises(Exception):
        Store(path, extra_migrations=[bad])

    # The store must still be openable, with the partial `notes` column rolled back
    # and the failed migration NOT recorded (so a corrected retry is possible).
    s = Store(path)
    cols = {r[1] for r in s.conn.execute("PRAGMA table_info(findings)").fetchall()}
    assert "notes" not in cols
    recorded = {r[0] for r in s.conn.execute("SELECT name FROM migrations").fetchall()}
    assert "0002_bad" not in recorded
    s.close()
