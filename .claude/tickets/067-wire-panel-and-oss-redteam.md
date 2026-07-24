---
id: 067
title: Wire the Judge panel + OSS red-team client into the live run (opt-in)
status: todo
depends_on: []
branch: ticket/067-wire-panel-and-oss-redteam
base_branch: main
test_command: ".venv/bin/pytest tests/test_live_wiring.py -q"
full_suite_command: ".venv/bin/pytest -q"
attempts: 0
---

## Description
Tickets 059 (Judge panel) and 060 (OSS/local red-team client) shipped as drop-in seams but are
not used by the deployed run. Wire both into `main()` behind OPT-IN env config so default prod
behavior is byte-for-byte unchanged: the Red Team LLM is built via the per-role
`build_llm_client` factory (so `FORGE_CLIENT_RED_TEAM=openai-compat` points it at a local/OSS
endpoint; default = Claude), and the Judge is a `JudgePanel` when `FORGE_JUDGE_PANEL` lists 2+
models (majority vote across diverse graders; default = the single Claude judge). Extract two
small tested builder functions so the wiring is unit-testable without network.

## Acceptance criteria
- [ ] `Config.from_env` gains `judge_models: list[str]` parsed from `FORGE_JUDGE_PANEL`
      (comma-separated model ids, stripped, empties dropped). Unset → `[]`. No other config
      behavior changes.
- [ ] `build_judge(llm, config)` returns: a `JudgePanel` of one `JudgeAgent` per model when
      `config.judge_models` has >= 2 entries (each member built on the SAME `llm`, with its own
      model id, in order); otherwise a single `JudgeAgent` on `config.judge_models[0]` if set,
      else on `config.models["judge"]` (the default).
- [ ] `build_red_team_llm(config, meter, *, claude_client=None, transport=None)` returns a
      `MeteredLLM` (sharing the passed `meter`) wrapping the client from
      `build_llm_client("red_team", config, ...)` — a `ClaudeClient` by default, or an
      `OpenAICompatClient` when `config.providers["red_team"]["kind"] == "openai-compat"`.
- [ ] `main()` uses `build_red_team_llm(config, meter)` for the Red Team LLM and
      `build_judge(judge_llm, config)` for the Judge, keeping the Judge on Claude. With NO new env
      vars set, `main()` builds exactly what it built before: a single Claude `JudgeAgent` on
      `models["judge"]` and a Claude-backed Red Team — no behavior change (existing run/entrypoint
      tests stay green).
- [ ] Cost still aggregates: both agents' LLMs are `MeteredLLM` sharing one `CostMeter`.

## Test plan (orchestrator authors these)
- unit (`tests/test_live_wiring.py`):
  - `Config.judge_models` parses `FORGE_JUDGE_PANEL="a, b ,c"` -> `["a","b","c"]`; unset -> `[]`.
  - `build_judge` default -> `JudgeAgent` on `models["judge"]`; panel env (>=2 models) -> `JudgePanel`
    whose members are `JudgeAgent`s with the listed models in order, all sharing the passed llm;
    single-model env -> a single `JudgeAgent` on that model.
  - `build_red_team_llm` default -> `MeteredLLM` wrapping `ClaudeClient` (inject `claude_client` to
    avoid the anthropic import), sharing the passed meter; `FORGE_CLIENT_RED_TEAM=openai-compat`
    (+ base_url, fake transport) -> `MeteredLLM` wrapping `OpenAICompatClient`.
