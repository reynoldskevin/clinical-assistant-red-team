---
name: plan-project
description: >-
  Turn a PROJECT_BRIEF.md into a defensible build. Reads the brief from the project
  root, asks clarifying questions, then generates ARCHITECTURE.md + ARCHITECTURE_DIAGRAM.md
  (gated for approval), and from the approved architecture a BUILD_PLAN.md (MVP-first,
  milestoned) and a TICKETS.md that feeds the tdd-ticket-loop skill. Trigger phrases:
  "plan the project", "plan this build", "turn the brief into a plan", "plan-project".
  Planning/architecture task — it writes docs and tickets, it does NOT write product code.
---

# Plan Project — brief → architecture → build plan → tickets

You (the main Claude Code agent) are the **project planner**. Your job is to turn a
`PROJECT_BRIEF.md` into a small set of planning artifacts that a build can execute
against: an architecture and diagram, a milestoned build plan, and a ticket list that
hands off to the **`tdd-ticket-loop`** skill. This is a **planning task** — you produce
documents and tickets, you do NOT write product/feature code here.

## Locked design decisions (do not deviate without asking the user)

1. **The brief is the single source of truth.** Every architecture and plan decision must
   trace back to something in `PROJECT_BRIEF.md` (or a clarifying answer the user gave).
   Do not invent scope; do not silently drop a requirement. If the brief and a user answer
   conflict, surface it and ask.
2. **Generic, not project-specific.** This skill depends ONLY on `PROJECT_BRIEF.md`. Do
   not hardcode artifact names, agent roles, or tech stacks from any one brief. Parse
   whatever sections the brief actually contains and map them to the canonical concepts
   below. Any brief-specific deliverable (e.g. a threat-model doc, a users doc, an evals
   directory) is scheduled **as a ticket/milestone in the build plan** — never baked into
   this skill.
3. **MVP-first, shortest path.** The build plan's first milestone(s) must be the minimum
   needed to satisfy the brief's **MVP Requirements** in the shortest time. Everything else
   required by the brief comes after. Nothing beyond MVP goes into the MVP milestone.
4. **Optional requirements are backlog — but never designed out.** Anything the brief marks
   optional (e.g. an "Optional …" section) goes to a **Backlog** section of the build plan,
   NOT the mainline milestones. BUT the mainline architecture must leave clean extension
   points so each optional item can be added later **without reworking mainline code**.
   Call these extension points out explicitly in ARCHITECTURE.md ("Extension points").
5. **Platform + engineering requirements are load-bearing.** The brief's Platform
   Requirements and (non-optional) Engineering Requirements constrain EVERY decision, at
   MVP and beyond. Treat them as invariants the architecture must satisfy, not features to
   bolt on. Each one must be visibly addressed in ARCHITECTURE.md.
6. **Submission requirements are tracked deliverables.** Every artifact the brief's
   Submission Requirements name must appear as an explicit deliverable in BUILD_PLAN.md
   (mapped to the milestone that produces it) and, where it needs building, as a ticket in
   TICKETS.md. None may be left implicit.
7. **Architecture gate.** After producing ARCHITECTURE.md + ARCHITECTURE_DIAGRAM.md,
   STOP and get the user's approval BEFORE generating BUILD_PLAN.md and TICKETS.md.
   Everything downstream derives from the architecture — get it right first.
8. **TICKETS.md is the single master index.** Write ONE `TICKETS.md`. Do NOT pre-create the
   individual `.claude/tickets/NNN-slug.md` files — the `tdd-ticket-loop` skill materializes
   those at run time from TICKETS.md. TICKETS.md must carry every field that skill needs so
   the handoff is 1:1 (see the TICKETS.md template).
9. **No code.** This skill writes `*.md` planning artifacts only. It does not implement
   features, scaffold repos, or run builds. Handoff to `tdd-ticket-loop` does that.

## Canonical brief concepts (map the brief's actual headings onto these)

Briefs vary in wording; identify each of these from `PROJECT_BRIEF.md` by meaning, not by
exact heading text. If one is absent, note it and proceed.

- **Scenario** — the narrative of what is being built and why.
- **Hard Problems** — the core engineering problems that are the focus; the architecture is
  judged on how deliberately it addresses these.
- **MVP Requirements** — the minimum foundation to stand up first (often staged).
- **Platform Requirements** — mandatory structural/architectural constraints.
- **Engineering Requirements** — mandatory cross-cutting requirements (graded, not optional).
- **Optional Engineering Deliverables** — nice-to-haves → backlog + extension points.
- **Submission Requirements** — the concrete artifacts that must be delivered.

## Preconditions

- `PROJECT_BRIEF.md` exists in the project root. If missing, STOP and ask the user for it —
  do not invent a brief.
- If `ARCHITECTURE.md` / `BUILD_PLAN.md` / `TICKETS.md` already exist, do not clobber blindly:
  read them, tell the user what's there, and confirm regenerate-vs-update before writing.

## Step 0 — Read and parse the brief

Read `PROJECT_BRIEF.md` in full. Extract, into a working outline you keep in-session:
the Scenario, every Hard Problem, every MVP requirement (preserving any staging), every
Platform requirement, every (non-optional) Engineering requirement, every Optional
deliverable, and every Submission artifact. Build a **requirements checklist** — one row
per requirement — that you will later map to architecture decisions, milestones, and
tickets so nothing is dropped. If the brief declares hard gates (must-submit-with-every-checkpoint
items), flag them as non-negotiable.

## Step 1 — Clarify (ask before you architect)

Ask the user a focused set of questions (batch them; use the AskUserQuestion tool where it
fits). Only ask what genuinely changes the architecture or plan — decide the rest from the
brief and sensible defaults, and state the defaults you took. Typical unknowns worth asking:

- Ambiguities or apparent contradictions in the brief.
- Tech stack / framework / language constraints not fixed by the brief, and existing code to
  build on vs. greenfield.
- Deployment target and any "must be live" gate.
- Time/effort budget and team size (drives how aggressively to trim the MVP and how granular
  tickets should be).
- Which optional deliverables (if any) the user wants treated as likely-to-happen (so the
  extension points get more attention), vs. pure backlog.
- The test runner / CI expectation (so TICKETS.md can specify real `test_command`s that
  `tdd-ticket-loop` will run).

Reflect the answers back into the requirements checklist before moving on.

## Step 2 — ARCHITECTURE.md + ARCHITECTURE_DIAGRAM.md  →  GATE

Write both files, then STOP for approval (decision #7).

**ARCHITECTURE.md** must cover ALL requirements in the checklist. Use the template below.
Every Hard Problem gets an explicit subsection saying how the design addresses it. Every
Platform and (non-optional) Engineering requirement is visibly satisfied. Optional items
appear ONLY under "Extension points" as future-facing hooks, not mainline design. If the
brief requires ARCHITECTURE.md to begin with a summary of a given length or to name
specific components, honor that exactly.

**ARCHITECTURE_DIAGRAM.md** holds the visual model — default to **Mermaid** fenced blocks
inside markdown (portable, diff-able, renders on most platforms). Include at least a
component/interaction diagram; add data-flow / sequence / trust-boundary diagrams when the
brief's problems call for them. Keep it consistent with ARCHITECTURE.md (same component
names).

Then present a short summary of the key decisions and **explicitly ask the user to approve
or request changes before you proceed to the build plan.** Do not write BUILD_PLAN.md or
TICKETS.md until they approve.

## Step 3 — BUILD_PLAN.md (after approval)

Derive the plan from the approved architecture. Use the template below. Rules:

- **Milestone 1 = shortest path to MVP.** Include only what the brief's MVP Requirements
  demand. If MVP is staged in the brief, mirror those stages as ordered sub-milestones.
- **Later milestones** cover the remaining brief requirements (Platform, Engineering,
  Submission artifacts) in dependency order, each with a clear exit criterion.
- **Backlog** holds every Optional deliverable, each annotated with the mainline extension
  point (from ARCHITECTURE.md) it will attach to — proving it can be added without conflict.
- **Deliverables map:** a table mapping every Submission Requirement artifact → the milestone
  that produces it. Nothing from the checklist may be missing.
- Each milestone lists concrete exit/acceptance criteria and its dependencies.

## Step 4 — TICKETS.md (feeds tdd-ticket-loop)

Break the milestones into the **smallest independently-testable** tickets, in dependency
order, MVP milestone first. Write ONE `TICKETS.md` (decision #8) using the template below.
Each ticket carries exactly the fields `tdd-ticket-loop` expects so it can materialize
`.claude/tickets/NNN-slug.md` 1:1 (`id`, `title`, `depends_on`, acceptance criteria, test
plan, plus the milestone tag and the `test_command`/`full_suite_command` you confirmed in
Step 1). Keep tickets small enough that each is a clean TDD unit with observable acceptance
criteria. Order so MVP is fully covered by the earliest tickets.

## Handoff

When TICKETS.md is done, tell the user the plan is ready and that they can run the
**`tdd-ticket-loop`** skill to execute it (it reads BUILD_PLAN.md / TICKETS.md and drives
sub-agents through TDD, one ticket at a time). Do not start the loop yourself unless asked.

## Templates

### ARCHITECTURE.md

```markdown
# Architecture — <project name>

## Summary
<Honor any length/opening the brief demands, e.g. "~500 word summary." Cover: what the
system is, the core design decisions, and how they answer the Hard Problems.>

## Goals & non-goals
- Goals: <traced to the brief>
- Non-goals: <explicitly out of scope, incl. optional items deferred to backlog>

## Requirements coverage
| Requirement (from brief) | Type (MVP/Platform/Engineering/Submission/Optional) | How the architecture satisfies it |
|---|---|---|
| … | … | … |

## Hard problems — how this design addresses each
### <Hard problem 1>
<deliberate, defensible approach + the evidence/reasoning behind it>
### <Hard problem 2>
…

## Components
<Each component: responsibility, inputs, outputs, trust level, and — for any component the
brief mandates — how it meets the mandate. Names MUST match ARCHITECTURE_DIAGRAM.md.>

## Interfaces & data flow
<How components communicate; message/contract shapes where the brief requires them;
where state lives.>

## Cross-cutting concerns
<Address each non-optional Engineering Requirement and each Platform Requirement explicitly:
security, cost/scale, observability, testing/regression, etc. — as the brief demands.>

## Extension points (for optional / future deliverables)
<For each Optional deliverable: the seam in the mainline design where it plugs in later
WITHOUT reworking mainline code. This is what lets backlog items be added if time allows.>

## Key tradeoffs & alternatives considered
<Decisions you can defend, with the alternative you rejected and why.>
```

### ARCHITECTURE_DIAGRAM.md

```markdown
# Architecture Diagram — <project name>

## Component / interaction diagram
```mermaid
flowchart TD
  %% components + how they interact; names match ARCHITECTURE.md
```

## Data flow
```mermaid
flowchart LR
  %% how data/messages move through the system
```

<Add sequence / trust-boundary diagrams as the brief's problems require.>
```

### BUILD_PLAN.md

```markdown
# Build Plan — <project name>

## Approach
<1–2 paragraphs: MVP-first, then remaining brief requirements; optional items in backlog
behind extension points.>

## Milestone 1 — MVP (shortest path)
Goal: satisfy the brief's MVP Requirements only.
- Scope: <bullets — nothing beyond MVP>
- Exit criteria: <observable, testable>
- Dependencies: <none / …>
  <If the brief stages the MVP, mirror those as ordered sub-milestones 1a, 1b, …>

## Milestone 2 — <next> …
Goal: <remaining brief requirement group>
- Scope / Exit criteria / Dependencies

<More milestones as needed, in dependency order.>

## Backlog (optional deliverables — build only if time allows)
| Optional deliverable | Extension point it attaches to (from ARCHITECTURE.md) |
|---|---|
| … | … |

## Deliverables map (Submission Requirements → milestone)
| Submission artifact | Produced by milestone |
|---|---|
| … | … |
```

### TICKETS.md

```markdown
# Tickets — <project name>

> Master index for the `tdd-ticket-loop` skill. Ordered by dependency; MVP milestone first.
> tdd-ticket-loop materializes each entry into `.claude/tickets/NNN-slug.md`.

## 001 — <title>
- id: 001
- milestone: 1 (MVP)
- depends_on: []
- test_command: "<exact command tdd-ticket-loop runs for this ticket>"
- full_suite_command: "<exact full-suite command>"

**Description**
<what & why, 2–4 lines>

**Acceptance criteria**
- [ ] <observable, testable behavior>
- [ ] …

**Test plan** (orchestrator authors these)
- unit: <files/cases>
- e2e: <files/cases, if applicable>

## 002 — <title>
- id: 002
- milestone: 1 (MVP)
- depends_on: [001]
…
```

## What this skill does NOT do

- No product/feature code. No repo scaffolding. No running the build.
- No inventing scope beyond the brief + clarifying answers.
- No skipping the architecture approval gate.
- No pre-writing individual ticket files (that's tdd-ticket-loop's job).
- No burying optional items in the mainline plan, and no designing them out of reach.
```