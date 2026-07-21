# Users — agent-forge-adversarial

agent-forge-adversarial is an autonomous multi-agent red-team platform that continuously attacks the OpenEMR AI Clinical Co-Pilot sidecar — a clinical-QA LLM agent that answers questions over patient charts — to find, confirm, and regression-guard security vulnerabilities. This document describes who the platform serves, how they work with it, the concrete scenarios it supports, and why an autonomous platform is the right tool for the job.

## Users / Personas

- **AI security engineer / red-team lead.** Owns the adversarial evaluation of the Co-Pilot before and after every release. Deep expertise in prompt injection, data exfiltration, and jailbreak techniques, but limited time. Needs the platform to generate and mutate attacks across categories, judge them independently, and surface only confirmed exploits so effort goes to real findings, not triage.

- **Healthcare platform / application security team.** Accountable for an LLM that touches PHI. Needs defensible assurance — mapped to the OWASP LLM Top 10 and compliance obligations — that the Co-Pilot will not leak protected data or be hijacked into unauthorized actions. They read reports more than they write attacks.

- **The Co-Pilot's own product and ML engineers.** They change system prompts and swap models frequently. They want a regression gate so a prompt or model change cannot silently reintroduce a previously fixed exploit.

- **Security researcher / analyst.** Reviews confirmed findings, validates severity, and approves what gets published into auditable vulnerability reports.

## Workflows

Users point the platform at the deployed target sidecar, then launch a run with `forge run --category <c>` for one of the six attack categories. From there the loop is autonomous: a directive is issued, the Red Team agent crafts and mutates multi-turn attacks, a Judge independently renders a verdict, confirmed exploits are recorded, and each is converted into a regression case. The live dashboard streams progress, coverage, and cost. Engineers review confirmed exploits and vulnerability reports, then gate a release on the regression suite passing. Researchers approve findings before they are published.

## Use cases

- **Pre-release adversarial sweep** across all six attack categories to clear a release candidate.
- **Continuous regression** after a system-prompt or model change, replaying every previously confirmed exploit to prove none regressed.
- **Auditable vulnerability report** generation for a compliance or security review.
- **OWASP LLM Top 10 coverage measurement**, showing which risk classes have been exercised and confirmed.
- **Cost forecasting** the evaluation at scale before committing to a larger continuous run.

## Why automation

The LLM attack surface is combinatorial and non-deterministic: effective attacks mutate, chain across multiple turns, and depend on model state a static test list cannot capture. A hand-written suite goes stale the moment prompts or models change, and a human red-teamer cannot sustain continuous, repeatable coverage cheaply. Autonomous agents that generate, judge, and convert attacks into regression cases give scalable, reproducible coverage, while humans stay in the loop to approve published findings. That combination is why this must be an autonomous multi-agent platform rather than manual pen-testing or a fixed test file.
