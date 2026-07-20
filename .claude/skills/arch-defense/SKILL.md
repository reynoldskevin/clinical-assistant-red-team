---
name: arch-defense
description: >-
  Generate an architecture-defense presentation from the plan-project deliverables. Companion
  to the plan-project skill: run it once ARCHITECTURE.md + ARCHITECTURE_DIAGRAM.md (and ideally
  BUILD_PLAN.md / TICKETS.md / PROJECT_BRIEF.md) exist. Produces a self-contained HTML slide
  deck (ARCHITECTURE_DEFENSE.html) and a presenter's demo script (DEMO_SCRIPT.md) that highlight
  and defend the key decisions from the architecture. Trigger phrases: "arch defense",
  "defend the architecture", "make the architecture presentation", "arch-defense".
  Presentation/communication task — it reads the plan docs and writes deck + script, no product code.
---

# Arch Defense — architecture-defense presentation generator

You (the main Claude Code agent) turn the **plan-project** deliverables into a presentation a
person can stand up and deliver: a self-contained **HTML slide deck** and an accompanying
**demo script** that highlight — and *defend* — the key decisions recorded in `ARCHITECTURE.md`
and `ARCHITECTURE_DIAGRAM.md`. This is a **communication task** — you read the plan docs and
write the deck + script; you do NOT write or change product code.

## Locked design decisions (do not deviate without asking the user)

1. **The architecture docs are the single source of truth.** Every slide claim and every talking
   point must trace to `ARCHITECTURE.md` / `ARCHITECTURE_DIAGRAM.md` (and, for context,
   `BUILD_PLAN.md` / `TICKETS.md` / `PROJECT_BRIEF.md`). Do NOT invent capabilities, components,
   or guarantees the architecture never made — an architecture defense collapses the moment you
   claim something you didn't design. If something important is missing from the docs, flag it to
   the user rather than inventing it.
2. **Companion to plan-project, generic.** This skill depends only on the plan-project outputs
   existing — it is not tied to any one project. Parse whatever those docs contain (components,
   hard problems, tradeoffs, extension points) and present them; do not hardcode a specific
   project's agents or stack.
3. **Defensibility over decoration.** The goal is to WIN a defense, not just look nice. Lead with
   the decision, the alternative rejected, and the reason — the deck's spine is the architecture's
   "Key tradeoffs & alternatives" plus how each Hard Problem is addressed. Anticipate challenge
   questions (that is what the demo script's Q&A section is for).
4. **Assume the audience knows the problem.** Do NOT spend slides re-explaining the scenario, the
   stakes, or why the problem matters — the audience already knows. Open on the architecture and
   spend the time on **core architecture decisions** and **unresolved unknowns / open questions**.
   No "problem & stakes" slide; only a one-line framing on the title slide if needed.
5. **Ruthlessly brief — a 5-minute talk, ~6 slides max.** This is a high-level summary of *how the
   system is being built* and *what drove the key decisions* — NOT a complete tour of the
   architecture or the brief. Do not try to address everything; cut anything that isn't (a) the
   shape of the system, (b) the decisions and their drivers, (c) the open unknowns, (d) the plan in
   one line. Default target: **~6 slides, ~5 minutes.** Only expand if the user asks for a longer
   talk. One idea per slide; short headlines, tight bullets, a visual per concept; depth lives in
   the speaker's demo script, not on the slide.
6. **Self-contained HTML.** `ARCHITECTURE_DEFENSE.html` must open in any browser with NO network:
   inline all CSS and JS, no external CDNs/fonts/scripts. Diagrams are embedded as **inline SVG**
   (hand-render simplified versions faithful to `ARCHITECTURE_DIAGRAM.md`'s component names) — do
   NOT depend on a Mermaid CDN. Keyboard-navigable (←/→, and a slide counter).
7. **Fixed output names.** Write exactly `ARCHITECTURE_DEFENSE.html` and `DEMO_SCRIPT.md` in the
   project root (these match the project's ignore patterns). Re-running overwrites them; if they
   exist, say so and confirm regenerate.
8. **No product code, no plan changes.** This skill only writes the deck + script. It does not
   edit `ARCHITECTURE.md`, run the build, or alter tickets.

## Preconditions

- `ARCHITECTURE.md` **and** `ARCHITECTURE_DIAGRAM.md` exist in the project root. If either is
  missing, STOP and tell the user to run **plan-project** first — do not fabricate an architecture.
- Read, if present, `BUILD_PLAN.md`, `TICKETS.md`, and `PROJECT_BRIEF.md` for context (the roadmap
  slide, the problem/stakes slide, and to know what the architecture was defending against).
- Note which other deliverables the brief named exist on disk (e.g. `THREAT_MODEL.md`, `./evals/`,
  reports, a deployed URL in README, running code) — this decides whether the demo is a **live
  demo** or an **architecture walkthrough** (see Step 3).

## Step 0 — Read and extract the defense points

Read `ARCHITECTURE.md` and `ARCHITECTURE_DIAGRAM.md` in full. Extract into a working outline:
the thesis/summary, each component + its role + trust level, each Hard Problem and how it's
addressed, the trust boundaries + human gates, the model/cost decisions, the extension points,
and — most important for a defense — the **key tradeoffs & alternatives considered**. Pull the
roadmap/MVP framing from `BUILD_PLAN.md` and the problem/stakes from `PROJECT_BRIEF.md`.

## Step 1 — Clarify (only what changes the deck)

Ask a short, batched set of questions only where the answer changes the output; otherwise take
sensible defaults and state them. Typical:
- **Audience & depth** (technical reviewers vs. mixed stakeholders) — sets slide density and jargon.
- **Time budget** — sets slide count. **Default is ~5 minutes / ~6 slides** (decision #5); only go
  longer if the user explicitly asks.
- **Live demo available?** — is there running code / a deployed URL to demo, or is this a pure
  architecture walkthrough? (You can also infer this from disk per Step 0.)
Default if unanswered: technical reviewers, **~5 minutes (~6 slides)**, live demo if runnable
code/URL exists else architecture walkthrough. State the defaults you took.

## Step 2 — ARCHITECTURE_DEFENSE.html (self-contained deck)

Write a self-contained HTML deck using the skeleton below. The audience already knows the problem
domain, and the talk is **~5 minutes / ~6 slides** — so this is a high-level summary, NOT a tour.
**Do NOT include a problem/stakes slide.** Fold what used to be many slides (roles, core loop, model
choices, cost, integrity, observability, extension points, tradeoffs) into a couple of dense
"decisions & drivers" slides — mention only what a reviewer needs to grasp *how it's built* and
*why*. Recommended ~6-slide flow (adapt; merge/cut to hold 5 minutes):

1. **Title** — project name + one-line thesis (the architecture's core bet). One line of framing;
   no scenario recap.
2. **How we're building it** — the component/interaction diagram (inline SVG) with named
   components; one line naming the two deterministic substrates. This is the "how" in one picture.
3. **What drove the decisions** — the 4–5 *driver → decision* pairs that define the architecture
   (e.g. "self-grading is compromised → independent Judge"; "frontier refusal + cost → Claude with
   a local/OSS seam + deterministic-first"; "autonomy in a live system → human gates"; "a fix must
   be real → replay + meaningful-pass"). This slide is the heart of the defense.
4. **Trust & integrity** *(optional 4th if time allows)* — the human gates + how a real fix is told
   from a behavior change, in a few bullets or the trust-boundary SVG. Merge into slide 3 if tight.
5. **Open questions & unknowns** — the few unresolved decisions / assumptions to validate, each with
   how it resolves (from the architecture's residual risks + anything the plan left open). Keep to
   3–4 items. An honest defense names what isn't settled.
6. **Roadmap + close** — MVP-first in one line (from BUILD_PLAN) and the single takeaway to remember.

Keep each slide to a headline + ≤5 tight bullets or one visual. Use the architecture's real
component names. After writing, verify (spot-check) that no slide asserts something absent from the
source docs, that no slide re-explains the problem, and that the whole deck reads in ~5 minutes.

## Step 3 — DEMO_SCRIPT.md (presenter's companion)

Write the speaker's script that runs alongside the deck. Sections:
- **At a glance** — audience, time budget, per-slide time allocation, one-line thesis to land.
- **Per-slide talking points — explain, don't read.** The slide is the headline; the script is the
  substance. For each slide, do NOT restate the bullets verbatim. Instead: say what the audience is
  looking at and interpret it — walk a diagram and name the flow, unpack a term the slide only
  labels, give the *why* behind a decision, connect it to the previous slide. Add information that
  is NOT on the slide. Use a light structure per slide — *on screen* (one line of what's shown) →
  *say / explain* (the spoken substance, ~2–4 sentences that add context) → the ONE point that must
  land. Assume the audience knows the problem — open on the architecture; do not script a
  problem/stakes recap. If a slide's talking point could be produced just by reading the slide, it's
  wrong — rewrite it to explain.
- **Live demo (or architecture walkthrough)** — if runnable code / a deployed URL exists: the exact
  commands to run (pull real commands from BUILD_PLAN/TICKETS, e.g. the run entrypoint), what to
  show, and the expected observable result — plus a **fallback** if the live demo fails (screenshot/
  recorded output to describe). If nothing is runnable yet: a step-by-step architecture walkthrough
  keyed to the diagrams, clearly labeled as a walkthrough, and the commands that WILL demo it once
  built.
- **Anticipated defense Q&A** — the tough questions a reviewer will ask about each major decision
  (drawn from the architecture's tradeoffs, trust boundaries, model choices, and known risks) with
  the crisp, defensible answer for each. This is the highest-value section — invest in it.
- **Open questions & unknowns** — the unresolved decisions and assumptions still to validate
  (e.g. an external contract not yet pinned, a choice deferred to a milestone, a parameter to tune),
  each with how you'll resolve it. Pair with **known risks & honest limitations** — what you'd say
  when asked "what's weakest here?" — taken from the architecture's residual risks / AI-use
  disclosure, each with its named mitigation. Owning these is more defensible than hiding them, and
  for a problem-aware audience this is where the discussion will actually go.

## Handoff

Tell the user both files are ready, how to present (open `ARCHITECTURE_DEFENSE.html` in a browser;
←/→ to navigate; the deck is self-contained and works offline), and that `DEMO_SCRIPT.md` is the
speaker companion. Optionally offer to publish the HTML as an Artifact (via the Artifact tool) if
they want a shareable hosted link — note the Artifact CSP requires the same fully-inlined,
self-contained page.

## HTML skeleton (self-contained deck)

Adapt freely; keep it inline-only, keyboard-navigable, and legible.

```html
<style>
  :root { --bg:#0b0f14; --fg:#e8eef5; --muted:#93a4b8; --accent:#5e8bff; --panel:#131a23; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html,body { height:100%; background:var(--bg); color:var(--fg);
    font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  .deck { height:100vh; overflow:hidden; }
  .slide { display:none; height:100vh; padding:6vh 8vw; flex-direction:column; justify-content:center; }
  .slide.active { display:flex; }
  h1 { font-size:clamp(28px,5vw,56px); line-height:1.1; margin-bottom:.4em; }
  h2 { font-size:clamp(22px,3.4vw,38px); color:var(--accent); margin-bottom:.6em; }
  .lead { font-size:clamp(18px,2.2vw,26px); color:var(--muted); max-width:60ch; }
  ul { margin:.4em 0 0 1.2em; max-width:70ch; } li { margin:.35em 0; font-size:clamp(15px,1.7vw,20px); }
  .kicker { color:var(--accent); letter-spacing:.14em; text-transform:uppercase; font-size:13px; margin-bottom:1em; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-top:1em; }
  .card { background:var(--panel); border:1px solid #23303f; border-radius:12px; padding:16px; }
  .card h3 { color:var(--accent); font-size:18px; margin-bottom:.3em; }
  svg { max-width:100%; height:auto; }
  .hud { position:fixed; bottom:16px; right:20px; color:var(--muted); font-size:13px; }
  .bar { position:fixed; top:0; left:0; height:3px; background:var(--accent); transition:width .2s; }
</style>

<div class="bar" id="bar"></div>
<div class="deck" id="deck">
  <section class="slide active"><div class="kicker">Architecture Defense</div>
    <h1><!-- project --></h1><p class="lead"><!-- one-line thesis --></p></section>
  <!-- one <section class="slide">…</section> per slide; embed diagrams as inline <svg> -->
</div>
<div class="hud"><span id="n">1</span> / <span id="tot">1</span></div>

<script>
  const s=[...document.querySelectorAll('.slide')]; let i=0;
  const tot=document.getElementById('tot'); tot.textContent=s.length;
  function show(n){ i=Math.max(0,Math.min(s.length-1,n));
    s.forEach((el,k)=>el.classList.toggle('active',k===i));
    document.getElementById('n').textContent=i+1;
    document.getElementById('bar').style.width=((i+1)/s.length*100)+'%'; }
  addEventListener('keydown',e=>{ if(e.key==='ArrowRight'||e.key===' ')show(i+1);
    if(e.key==='ArrowLeft')show(i-1); if(e.key==='Home')show(0); if(e.key==='End')show(s.length-1); });
  addEventListener('click',e=>{ if(!e.target.closest('a'))show(i+1); }); show(0);
</script>
```

## What this skill does NOT do

- No product/feature code. No changes to ARCHITECTURE.md or any plan doc.
- No claims not grounded in the plan-project deliverables.
- No external dependencies in the HTML (no CDNs/fonts/scripts) — fully self-contained.
- No inventing an architecture — if the docs are missing, it stops and points at plan-project.
