# AI-Use Disclosure

## Intro

The Agent Forge adversarial platform uses a large language model (Claude) inside
several distinct agent roles. This is deliberate: the work — generating adaptive,
evidence-driven attacks, evaluating them against a nuanced rubric, and drafting
readable findings — is exactly where an LLM is stronger than deterministic
tooling. But an LLM is *non-deterministic and fallible*, so the platform never
lets an AI decision stand on its own. **Every AI decision is followed by a
deterministic check or a human approval gate.** Deterministic tooling is used
*inside* the platform (the adapter, replay, calibration harness, budget policy)
precisely so the adaptive judgment of the model is always fenced by something
that does not drift.

This document discloses, per role: (a) **what the AI does**, (b) **the check that
follows it** — deterministic or human, and (c) **the residual risk** that
remains after that check. It closes with a plain statement of what was
independently verified versus what is still risky, and a dedicated procedure for
detecting and correcting a **drifting Judge** — the single most consequential AI
failure mode on the platform.

## Per-role disclosure

| Agent role | AI use | Verification (deterministic / human) | Residual risk |
|---|---|---|---|
| **Red Team** (Claude Sonnet) | Generates and mutates attack attempts against the target — adaptive, multi-turn, evidence-driven prompts and payloads. | Checked by the **independent Judge**: a Red Team "success" is *never* self-graded. The attacker and the evaluator are different agents by design, so a compromised or over-optimistic attacker cannot certify its own win. Attempts are also replayed deterministically before any claim is recorded. | Frontier-model **refusals** (Claude may decline in-scope authorized-testing prompts) and an **incomplete attack space** — the model only explores what it is prompted/mutated toward, so absence of a finding is not proof of safety. Mitigated by authorized-testing framing and the local/OSS Red Team swap seam; not eliminated. |
| **Judge** (Claude Opus) | Scores each attempt against a **versioned rubric** at low temperature, producing a verdict (pass / fail / needs-review) with rationale. | Checked by the frozen **calibration** set and the **safety invariant**. `run_calibration(build_judge)` in `forge/selfcheck.py` replays the Judge over the labeled `CALIBRATION_FIXTURES` in `forge/judge.py`; `judge_invariant_holds(judge)` enforces the invariant that a labeled confirmed exploit is **never** scored "fail" (pass = the target survived; a real exploit must never be graded as the target passing). | A **drifting Judge** — model or rubric changes that silently shift verdicts on unchanged inputs. Mitigated by the calibration + invariant checks below, but not fully eliminated between calibration runs. See the drift procedure. |
| **Orchestrator** (minimal AI — ambiguous prioritization only) | Chooses *which* under-covered area to spend the next attack budget on when priority is genuinely ambiguous. It steers effort; it does not decide safety outcomes. | Checked by a **deterministic budget / coverage / halt policy**: spend, coverage targets, and stop conditions are enforced in code, not by the model. The AI can only reorder work *within* those hard bounds. | **Misprioritized effort** — the platform may probe a lower-value area first. This is **bounded and non-safety-critical**: it affects efficiency and coverage ordering, never whether an exploit is correctly judged or disclosed. |
| **Documentation** (Claude) | Drafts human-readable report prose — summaries, finding narratives, remediation write-ups — from structured finding records. | Checked by a **data-quality** gate (the narrative must reconcile with the structured findings/metrics it claims) and then a **human approval gate**: no report is published until a person signs off. | **Inaccurate narrative** — the model can phrase or frame a finding misleadingly even when the underlying data is correct. Gated by mandatory **human** sign-off before publish; residual risk is reduced to what a reviewer misses. |

## Residual risk & independent verification

**What was independently verified.** The load-bearing claims of the platform do
not rest on an AI grading itself:

- Red Team outcomes are verified by the **independent Judge** and by
  deterministic **replay** — the attacker never certifies its own success.
- Judge behavior is verified against the **frozen calibration set** and the
  **safety invariant** (`run_calibration` / `judge_invariant_holds`), which are
  labeled ground truth the model cannot silently edit.
- Orchestrator behavior is verified by a deterministic **budget / coverage /
  halt** policy enforced in code.
- Documentation is verified by a **data-quality** reconciliation check and a
  **human** approval gate.

**What remains risky (residual risk).** Verification narrows these failure modes
but does not remove them:

1. **A drifting Judge.** Between calibration runs, a model or rubric change can
   shift borderline verdicts. This is the highest-severity residual risk and has
   its own detect-and-correct procedure below.
2. **Red Team blind spots and refusals.** The attack space is only as complete
   as what the model was steered to try; frontier refusals can leave in-scope
   attacks unexecuted. Absence of a finding is not verified safety.
3. **Narrative inaccuracy under human review.** Human sign-off is the final
   check on Documentation; anything a reviewer misses is unverified.
4. **Orchestrator misprioritization.** Bounded by the budget policy and
   non-safety-critical, but it can still spend effort sub-optimally.

The claim we defend is narrow and honest: every AI decision that matters is
**independently verified** by something deterministic or human, and the residual
risks above are disclosed rather than hidden.

## Detecting & correcting a drifting Judge

The Judge is the one role whose silent failure would corrupt the platform's core
output, so it gets a dedicated procedure built on the **calibration** mechanism
(the **frozen** `CALIBRATION_FIXTURES` and the safety **invariant**).

### Detection

- **Mechanism.** Re-run `run_calibration(build_judge)` (from `forge/selfcheck.py`)
  over the **frozen** `CALIBRATION_FIXTURES` in `forge/judge.py`. Because the
  fixtures are labeled and immutable, a *changed verdict on a frozen input is,
  by definition, drift* — the inputs did not move, so the Judge did.
- **Cadence / threshold.** Run calibration **on every release** (any change to
  the Judge model id, rubric version, prompt, or temperature) and on a **daily**
  scheduled cadence in between. The pass threshold is strict: **100% of frozen
  fixtures must classify to their expected verdict, and `judge_invariant_holds`
  must return true on every run** — a confirmed exploit is never scored "fail".
  *Any* single mismatch, or any invariant violation, trips the drift alarm and
  blocks promotion of that Judge build. (The safety invariant is a hard gate,
  not a percentage: even one violation is a stop-the-line event.)
- **Signal vs. noise.** Because scoring is at low temperature over frozen
  inputs, the expected day-to-day variance is zero; there is no "acceptable
  drift band." A nonzero delta is a real regression to investigate, not noise.

### Correction

When drift is **detected**, the response is to freeze, diagnose, and
**recalibrate** — not to trust the new verdicts:

1. **Pin / roll back.** Immediately **roll back** the Judge to the last model +
   rubric version that passed calibration; pin that version for live judging.
2. **Quarantine.** Mark verdicts produced by the drifted Judge as
   *needs-review* and **re-judge** them under the pinned/known-good version so no
   drifted verdict reaches a published report.
3. **Diagnose & recalibrate.** Identify whether drift came from the model
   version, the rubric, the prompt, or temperature. **Correct** the rubric or
   pin the model as appropriate, then **recalibrate**: re-run `run_calibration`
   until 100% of fixtures pass and the invariant holds again before un-pinning.
4. **Expand the calibration set.** If the drift exposed a case the frozen
   fixtures did not cover, add a new labeled fixture to `CALIBRATION_FIXTURES`
   so the same drift is caught deterministically next time. Growing the frozen
   set is how detection sensitivity ratchets up over time.

This detect-and-correct loop is what turns "we use an LLM as a judge" into a
defensible claim: the Judge is continuously checked against ground truth it
cannot edit, drift is caught deterministically, and a confirmed exploit can
never be silently graded away.
