"""Acceptance tests for fix 029 — runnable module entrypoint (`python -m forge`).

The first Railway deploy crashed with `forge: command not found` because the
console script was not on the runtime PATH. The portable fix runs the app as a
module. These tests pin that contract:
- `python -m forge <args>` dispatches to `forge.run.main`.
- `python -m forge run` (no target flags) exits 2 with the guidance message,
  needing no API key/config — a real, non-blocking end-to-end check of the
  entrypoint that would have caught the crash.
- the `Procfile` launches the dashboard via the module form.
"""

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_python_dash_m_forge_reaches_main_and_parses_args():
    # `run` with no --category/--suite returns 2 BEFORE any config/API-key use,
    # so this proves the module entrypoint reaches main() and parses args.
    proc = subprocess.run(
        [sys.executable, "-m", "forge", "run"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert "specify --category" in (proc.stdout + proc.stderr)


def test_python_dash_m_forge_has_serve_subcommand():
    # The serve subcommand must be reachable via the module entrypoint too.
    proc = subprocess.run(
        [sys.executable, "-m", "forge", "--help"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "serve" in (proc.stdout + proc.stderr)


def test_procfile_uses_module_entrypoint():
    procfile = (REPO / "Procfile").read_text()
    assert "python -m forge serve" in procfile
    # must NOT rely on the bare console script that wasn't on PATH
    assert "web: forge serve" not in procfile
