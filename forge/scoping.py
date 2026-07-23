"""Run-scoping helpers shared by the dashboard and the autonomous runner.

Both the live dashboard and the Orchestrator need to view the store through the
lens of a single run: events by their id window and findings/cost rows by the
``run_id`` the runner stamps on them. This module holds that logic as public
names so callers (dashboard, run) share one implementation.
"""

from __future__ import annotations


def current_run(events):
    """``(start_id, end_id_or_None, version)`` of the latest run, or ``None``.

    ``start_id`` is the id of the newest ``run_start``; ``end_id`` the matching
    ``run_end`` (``None`` while the run is still active).
    """
    start_id = None
    version = None
    for ev in events:
        if ev.get("kind") == "run_start":
            eid = ev.get("id")
            if eid is not None and (start_id is None or eid > start_id):
                start_id, version = eid, ev.get("version")
    if start_id is None:
        return None
    end_id = None
    for ev in events:
        if ev.get("kind") == "run_end":
            eid = ev.get("id")
            if eid is not None and eid > start_id:
                end_id = eid if end_id is None else max(end_id, eid)
    return start_id, end_id, version


class RunScopedStore:
    """Read-only store view limited to a single run's records.

    Events are scoped by the id window ``[start_id, end_id]`` (open-ended while
    the run is active); findings and cost rows — which carry no event id — are
    scoped by the ``run_id`` the runner stamps on them.
    """

    def __init__(self, store, *, start_id, end_id):
        self._store = store
        self._start = start_id
        self._end = end_id

    def _in_window(self, eid):
        if eid is None or eid < self._start:
            return False
        return self._end is None or eid <= self._end

    def get_events(self):
        return [e for e in self._store.get_events() if self._in_window(e.get("id"))]

    def list_findings(self, **filters):
        return [
            f
            for f in self._store.list_findings(**filters)
            if f.get("run_id") == self._start
        ]

    def get_costs(self):
        return [c for c in self._store.get_costs() if c.get("run_id") == self._start]
