"""Acceptance tests for ticket 067 — wire Judge panel + OSS red-team into the live run.

Both are OPT-IN via env, so the default `main()` build is byte-for-byte the old one: a single
Claude JudgeAgent and a Claude-backed Red Team. These pin the two extracted builders.
"""

from forge.config import Config
from forge.run import build_judge, build_red_team_llm, MeteredLLM, CostMeter
from forge.judge import JudgeAgent, JudgePanel
from forge.llm import ClaudeClient, OpenAICompatClient


_BASE_ENV = {"ANTHROPIC_API_KEY": "sk-test", "TARGET_BASE_URL": "http://target"}


def _cfg(**extra):
    env = dict(_BASE_ENV)
    env.update(extra)
    return Config.from_env(env)


class _FakeTransport:
    def __call__(self, url, body):
        return {"model": "m", "choices": [{"message": {"content": "x"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def test_judge_models_parsed_from_env():
    assert _cfg(FORGE_JUDGE_PANEL="a, b ,c").judge_models == ["a", "b", "c"]
    assert _cfg().judge_models == []


# --------------------------------------------------------------------------- #
# build_judge
# --------------------------------------------------------------------------- #
def test_build_judge_default_is_single_claude_judge():
    cfg = _cfg()
    llm = object()
    j = build_judge(llm, cfg)
    assert isinstance(j, JudgeAgent)
    assert j._model == cfg.models["judge"]


def test_build_judge_panel_when_two_or_more_models():
    cfg = _cfg(FORGE_JUDGE_PANEL="claude-opus-4-8,claude-sonnet-5,claude-haiku-4-5-20251001")
    llm = object()
    j = build_judge(llm, cfg)
    assert isinstance(j, JudgePanel)
    members = j._members
    assert [m._model for m in members] == [
        "claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001"
    ]
    assert all(isinstance(m, JudgeAgent) for m in members)
    # one client serves the whole panel
    assert all(m._llm is llm for m in members)


def test_build_judge_single_model_env_is_single_judge():
    cfg = _cfg(FORGE_JUDGE_PANEL="only-model")
    j = build_judge(object(), cfg)
    assert isinstance(j, JudgeAgent)
    assert j._model == "only-model"


# --------------------------------------------------------------------------- #
# build_red_team_llm
# --------------------------------------------------------------------------- #
def test_build_red_team_llm_default_is_metered_claude():
    cfg = _cfg()
    meter = CostMeter()
    rt = build_red_team_llm(cfg, meter, claude_client=object())
    assert isinstance(rt, MeteredLLM)
    assert isinstance(rt._inner, ClaudeClient)
    assert rt._meter is meter


def test_build_red_team_llm_openai_compat_when_configured():
    cfg = _cfg(FORGE_CLIENT_RED_TEAM="openai-compat",
               FORGE_CLIENT_RED_TEAM_BASE_URL="http://localhost:11434")
    rt = build_red_team_llm(cfg, CostMeter(), transport=_FakeTransport())
    assert isinstance(rt, MeteredLLM)
    assert isinstance(rt._inner, OpenAICompatClient)
