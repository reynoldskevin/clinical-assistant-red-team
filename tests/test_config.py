"""Acceptance tests for ticket 001 — project scaffold & config.

These tests are the fixed contract for the config layer. They pin the public API:
- `import forge` works (package is importable)
- `from forge.config import Config, ConfigError`
- `Config.from_env(env)` — a classmethod that reads a mapping (defaults to os.environ),
  validates required vars, and applies per-role model + budget defaults with env overrides.
"""

import pytest


REQUIRED = {
    "ANTHROPIC_API_KEY": "sk-test-123",
    "TARGET_BASE_URL": "https://copilot.example.test",
}

ROLES = ("orchestrator", "red_team", "judge", "documentation")


def test_package_imports():
    import forge  # noqa: F401

    assert forge is not None


def test_from_env_loads_required_values():
    from forge.config import Config

    cfg = Config.from_env(dict(REQUIRED))
    assert cfg.anthropic_api_key == "sk-test-123"
    assert cfg.target_base_url == "https://copilot.example.test"


@pytest.mark.parametrize("missing", sorted(REQUIRED))
def test_missing_required_var_raises_config_error(missing):
    from forge.config import Config, ConfigError

    env = dict(REQUIRED)
    del env[missing]
    with pytest.raises(ConfigError) as exc:
        Config.from_env(env)
    # the error should name the offending variable
    assert missing in str(exc.value)


def test_config_error_is_distinct_exception_type():
    from forge.config import ConfigError

    assert issubclass(ConfigError, Exception)
    # not just a bare Exception alias
    assert ConfigError is not Exception


def test_optional_vars_default_cleanly():
    from forge.config import Config

    cfg = Config.from_env(dict(REQUIRED))
    assert cfg.target_auth is None
    assert isinstance(cfg.db_path, str) and cfg.db_path  # a non-empty default path


def test_optional_vars_read_from_env():
    from forge.config import Config

    env = dict(REQUIRED, TARGET_AUTH="Bearer abc", DB_PATH="/tmp/forge.db")
    cfg = Config.from_env(env)
    assert cfg.target_auth == "Bearer abc"
    assert cfg.db_path == "/tmp/forge.db"


def test_per_role_model_defaults_present():
    from forge.config import Config

    cfg = Config.from_env(dict(REQUIRED))
    for role in ROLES:
        assert role in cfg.models
        assert isinstance(cfg.models[role], str) and cfg.models[role]


def test_per_role_model_override_from_env():
    from forge.config import Config

    env = dict(REQUIRED, FORGE_MODEL_JUDGE="claude-custom-judge")
    cfg = Config.from_env(env)
    assert cfg.models["judge"] == "claude-custom-judge"
    # unrelated roles keep their defaults
    assert cfg.models["red_team"] != "claude-custom-judge"


def test_budget_defaults_present_and_numeric():
    from forge.config import Config

    cfg = Config.from_env(dict(REQUIRED))
    assert "per_run_usd" in cfg.budgets
    assert "per_directive_usd" in cfg.budgets
    assert cfg.budgets["per_run_usd"] > 0
    assert cfg.budgets["per_directive_usd"] > 0


def test_budget_override_from_env():
    from forge.config import Config

    env = dict(REQUIRED, FORGE_BUDGET_PER_RUN_USD="12.5")
    cfg = Config.from_env(env)
    assert cfg.budgets["per_run_usd"] == pytest.approx(12.5)


def test_from_env_defaults_to_process_environ(monkeypatch):
    from forge.config import Config

    for k, v in REQUIRED.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("TARGET_AUTH", raising=False)
    cfg = Config.from_env()  # no arg → reads os.environ
    assert cfg.anthropic_api_key == "sk-test-123"
