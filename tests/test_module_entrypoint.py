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
import re
import subprocess
import sys
import tomllib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _pkg_name(spec: str) -> str:
    # "anthropic>=0.40" -> "anthropic"
    return re.split(r"[<>=!~ \[]", spec.strip(), maxsplit=1)[0].lower()


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


def test_requirements_mirror_pyproject():
    # The Nixpacks build installs from requirements.txt; it must list every
    # runtime dependency declared in pyproject so the container isn't missing
    # modules at import (the second crash: `No module named 'pydantic'`).
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    declared = {_pkg_name(d) for d in pyproject["project"]["dependencies"]}

    reqs = (REPO / "requirements.txt").read_text().splitlines()
    listed = {
        _pkg_name(line) for line in reqs if line.strip() and not line.strip().startswith("#")
    }
    missing = declared - listed
    assert not missing, f"requirements.txt missing runtime deps: {missing}"
