"""Acceptance tests for ticket 058 — store data-quality, indexing, retention.

Pins:
- a new migration adds indexes on events(kind) and findings(status), and promotes
  ``run_id`` to a NATIVE indexed column on findings and cost (backfilled from the JSON blob),
- ``run_id`` stays readable through the existing JSON read surface (scoping keeps working),
- insert-time data-quality validation rejects invalid findings / kind-less events,
- an opt-in ``prune`` retention job trims events/cost by id watermark and never touches findings.
"""

import json
import sqlite3

import pytest

from forge.store import Store


def _index_names(store, table):
    return {r["name"] for r in store.conn.execute(f"PRAGMA index_list('{table}')").fetchall()}


def _columns(store, table):
    return {r["name"] for r in store.conn.execute(f"PRAGMA table_info('{table}')").fetchall()}


# --------------------------------------------------------------------------- #
# 1. migration: indexes + native run_id columns
# --------------------------------------------------------------------------- #
def test_new_indexes_and_run_id_columns_present():
    s = Store(":memory:")
    # migration count grew beyond the single baseline
    assert s.schema_version() >= 2
    # hot-path indexes
    assert "idx_events_kind" in _index_names(s, "events")
    assert "idx_findings_status" in _index_names(s, "findings")
    # native run_id columns + their indexes
    assert "run_id" in _columns(s, "findings")
    assert "run_id" in _columns(s, "cost")
    assert "idx_findings_run_id" in _index_names(s, "findings")
    assert "idx_cost_run_id" in _index_names(s, "cost")
    # the original findings indexes still exist
    fidx = _index_names(s, "findings")
    assert {"idx_findings_severity", "idx_findings_attack_category", "idx_findings_target_version"} <= fidx


def test_run_id_written_native_and_readable():
    s = Store(":memory:")
    fid = s.insert_finding(
        {"severity": "high", "attack_category": "prompt_injection",
         "status": "open", "target_version": "v1", "run_id": "R1"}
    )
    # stored in the native column
    raw = s.conn.execute("SELECT run_id FROM findings WHERE id=?", (fid,)).fetchone()
    assert raw["run_id"] == "R1"
    # still exposed through the read surface (scoping relies on this)
    assert s.get_finding(fid)["run_id"] == "R1"
    assert s.list_findings(severity="high")[0]["run_id"] == "R1"

    cid = s.insert_cost({"run_id": "R1", "usd": 0.25})
    craw = s.conn.execute("SELECT run_id FROM cost WHERE id=?", (cid,)).fetchone()
    assert craw["run_id"] == "R1"
    assert s.get_costs()[-1]["run_id"] == "R1"


# --------------------------------------------------------------------------- #
# 2. backfill of pre-existing (legacy 0001-schema) rows
# --------------------------------------------------------------------------- #
def _make_legacy_db(path):
    """A database at the 0001 baseline: findings/cost carry run_id ONLY in the JSON blob."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE migrations (name TEXT UNIQUE);
        INSERT INTO migrations (name) VALUES ('0001_baseline');
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY, severity TEXT, attack_category TEXT,
            target_version TEXT, status TEXT, data TEXT
        );
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, data TEXT);
        CREATE TABLE cost (id INTEGER PRIMARY KEY, data TEXT);
        """
    )
    conn.execute(
        "INSERT INTO findings (severity, attack_category, target_version, status, data) "
        "VALUES (?,?,?,?,?)",
        ("high", "prompt_injection", "v1", "open", json.dumps({"run_id": "LEGACY", "x": 1})),
    )
    conn.execute("INSERT INTO cost (data) VALUES (?)", (json.dumps({"run_id": "LEGACY", "usd": 0.1}),))
    conn.commit()
    conn.close()


def test_legacy_rows_backfilled_on_migration(tmp_path):
    path = str(tmp_path / "legacy.db")
    _make_legacy_db(path)
    # opening the Store applies the new migration, which must backfill run_id
    s = Store(path)
    assert s.schema_version() >= 2
    frow = s.conn.execute("SELECT run_id FROM findings").fetchone()
    assert frow["run_id"] == "LEGACY"
    crow = s.conn.execute("SELECT run_id FROM cost").fetchone()
    assert crow["run_id"] == "LEGACY"
    # rows preserved, other data intact
    assert s.list_findings()[0]["attack_category"] == "prompt_injection"
    s.close()


# --------------------------------------------------------------------------- #
# 3. data-quality validation on insert
# --------------------------------------------------------------------------- #
def test_insert_finding_rejects_missing_or_invalid_severity():
    s = Store(":memory:")
    with pytest.raises(ValueError):
        s.insert_finding({"attack_category": "prompt_injection", "status": "open"})
    with pytest.raises(ValueError):
        s.insert_finding({"severity": "", "attack_category": "x", "status": "open"})
    with pytest.raises(ValueError):
        s.insert_finding({"severity": "bogus", "attack_category": "x", "status": "open"})
    # nothing persisted
    assert s.list_findings() == []


def test_append_event_rejects_missing_kind():
    s = Store(":memory:")
    with pytest.raises(ValueError):
        s.append_event({"attempt_id": 1})
    with pytest.raises(ValueError):
        s.append_event({"kind": "", "attempt_id": 1})
    assert s.get_events() == []


def test_valid_rows_still_insert():
    s = Store(":memory:")
    for sev in ("critical", "high", "medium", "low"):
        fid = s.insert_finding({"severity": sev, "attack_category": "c", "status": "open"})
        assert s.get_finding(fid)["severity"] == sev
    eid = s.append_event({"kind": "verdict", "attempt_id": 7})
    assert eid > 0
    assert s.get_events()[-1]["kind"] == "verdict"


# --------------------------------------------------------------------------- #
# 4. retention batch job
# --------------------------------------------------------------------------- #
def test_prune_trims_events_and_cost_only():
    s = Store(":memory:")
    # findings must survive pruning
    fid = s.insert_finding({"severity": "high", "attack_category": "c", "status": "open"})
    ids = [s.append_event({"kind": "attack", "n": i}) for i in range(5)]
    for i in range(5):
        s.insert_cost({"run_id": "R", "usd": 0.01, "n": i})

    watermark = ids[2]  # keep events with id > watermark
    removed = s.prune(before_id=watermark)
    assert removed >= 3  # the 3 events with id <= watermark (cost rows counted too)

    remaining = [e["id"] for e in s.get_events()]
    assert all(i > watermark for i in remaining)
    # findings untouched
    assert s.get_finding(fid) is not None

    # idempotent: pruning again to the same watermark removes nothing new
    assert s.prune(before_id=watermark) == 0
