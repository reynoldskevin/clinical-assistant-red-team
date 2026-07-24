"""Typed configuration loaded from the environment.

Standard-library only. The public surface is :class:`Config` and
:class:`ConfigError`, as pinned by ``tests/test_config.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional

# Required environment variables (no sane default is possible).
_REQUIRED = ("ANTHROPIC_API_KEY", "TARGET_BASE_URL")

# Per-role model id defaults. Overridable via FORGE_MODEL_<ROLE_UPPER>.
_MODEL_DEFAULTS = {
    "orchestrator": "claude-opus-4-8",
    "red_team": "claude-sonnet-5",
    "judge": "claude-opus-4-8",
    "documentation": "claude-sonnet-5",
}

# Budget defaults (USD). Overridable via FORGE_BUDGET_<KEY_UPPER>.
_BUDGET_DEFAULTS = {
    "per_run_usd": 10.0,
    "per_directive_usd": 2.0,
}

_DEFAULT_DB_PATH = "forge.db"


class ConfigError(Exception):
    """Raised when configuration is missing or invalid.

    A distinct exception type (not an alias of :class:`Exception`) so callers
    can catch configuration problems specifically.
    """


@dataclass
class Config:
    """Validated, typed application configuration."""

    anthropic_api_key: str
    target_base_url: str
    target_auth: Optional[str] = None
    db_path: str = _DEFAULT_DB_PATH
    models: dict = field(default_factory=dict)
    budgets: dict = field(default_factory=dict)
    providers: dict = field(default_factory=dict)
    judge_models: list = field(default_factory=list)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Config":
        """Build a :class:`Config` from a mapping (defaults to ``os.environ``).

        Raises :class:`ConfigError` naming the first missing required variable.
        """
        if env is None:
            env = os.environ

        for name in _REQUIRED:
            value = env.get(name)
            if not value:
                raise ConfigError(
                    f"Missing required configuration variable: {name}"
                )

        models = {
            role: env.get(f"FORGE_MODEL_{role.upper()}", default)
            for role, default in _MODEL_DEFAULTS.items()
        }

        budgets = {
            key: _parse_float(
                env.get(f"FORGE_BUDGET_{key.upper()}"), default, key
            )
            for key, default in _BUDGET_DEFAULTS.items()
        }

        providers = {
            role: {
                "kind": env.get(f"FORGE_CLIENT_{role.upper()}", "claude"),
                "base_url": env.get(f"FORGE_CLIENT_{role.upper()}_BASE_URL"),
            }
            for role in _MODEL_DEFAULTS
        }

        judge_models = [
            m.strip()
            for m in (env.get("FORGE_JUDGE_PANEL") or "").split(",")
            if m.strip()
        ]

        return cls(
            anthropic_api_key=env["ANTHROPIC_API_KEY"],
            target_base_url=env["TARGET_BASE_URL"],
            target_auth=env.get("TARGET_AUTH"),
            db_path=env.get("DB_PATH") or _DEFAULT_DB_PATH,
            models=models,
            budgets=budgets,
            providers=providers,
            judge_models=judge_models,
        )


def resolve_reports_dir(env: Optional[Mapping[str, str]] = None) -> str:
    """Resolve the vuln-report directory, volume-aware.

    Precedence:
      1. A non-blank ``FORGE_REPORTS_DIR`` is returned verbatim.
      2. If a Railway volume is mounted (``RAILWAY_VOLUME_MOUNT_PATH``),
         default to ``<mount>/reports`` so reports survive redeploys.
      3. Otherwise the plain relative ``"reports"`` (local dev default).
    """
    if env is None:
        env = os.environ

    explicit = env.get("FORGE_REPORTS_DIR")
    if explicit is not None and explicit.strip():
        return explicit

    mount = env.get("RAILWAY_VOLUME_MOUNT_PATH")
    if mount:
        return os.path.join(mount, "reports")

    return "reports"


def _parse_float(raw: Optional[str], default: float, key: str) -> float:
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"Invalid numeric value for budget {key!r}: {raw!r}"
        ) from exc
