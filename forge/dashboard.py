"""Live demo dashboard (ticket 029) — `forge serve`.

A stdlib-only HTTP dashboard over the 016 observability read-model. It renders
the approved bento-grid design (accent #2968e6, theme-aware) from the live store
and auto-refreshes by polling ``GET /api/state``. Zero new dependencies
(``http.server``), no ``ANTHROPIC_API_KEY`` required — it reads only the store.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from forge.observability import Observability
from forge.store import Store  # noqa: F401  (documents the store dependency)


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #
def build_state(observability) -> dict:
    """A JSON-serializable state dict: the six 016 views + a ``kpis`` summary."""
    state = observability.snapshot()
    overall = observability.pass_fail()["overall"]
    cost = observability.cost()
    state["kpis"] = {
        "resilience": overall["pass_rate"],
        "attempts": overall["attempts"],
        "exploits": overall["exploits"],
        "total_usd": cost["total_usd"],
        "usd_per_attempt": cost["usd_per_attempt"],
    }
    # aggregate verdict outcomes for the outcome tile (always populated, unlike
    # the finding lifecycle which is empty until an exploit creates a finding).
    state["outcomes"] = {
        "exploited": overall["exploits"],
        "partial": overall["partial"],
        "defended": overall["defended"],
    }
    # single pass over events for: seq -> verdict (so the live feed can pill
    # verdict rows — the 016 activity log carries only seq/agent/kind/category),
    # and the run-in-progress flag (a run_start with no later run_end). Kept
    # separate from agent_activity, which mirrors the snapshot verbatim.
    verdicts = {}
    last_start = last_end = -1
    for ev in observability.store.get_events():
        kind = ev.get("kind")
        if kind == "verdict":
            verdicts[str(ev.get("id"))] = ev.get("verdict")
        elif kind == "run_start":
            last_start = ev.get("id", last_start)
        elif kind == "run_end":
            last_end = ev.get("id", last_end)
    state["verdicts"] = verdicts
    state["run_active"] = last_start > last_end
    return state


# --------------------------------------------------------------------------- #
# HTML — the approved gallery design, data-driven
# --------------------------------------------------------------------------- #
_STYLE = """
  :root {
    /* neutrals — slate with a slight cool bias, deliberately not pure grey */
    --bg: #0b0f16;
    --panel: #121826;
    --panel-2: #0e1420;
    --line: #1e2637;
    --line-soft: #171f2d;
    --fg: #e7edf6;
    --muted: #8493ac;
    --faint: #58657e;
    /* accent — brand blue #2968e6 (same value in both themes) */
    --accent: #2968e6;
    --accent-solid: #2968e6;
    --accent-dim: #24457f;
    /* semantic — verdict language (independent of the accent) */
    --good: #35d29b;   /* defended  */
    --warn: #f2b23e;   /* partial   */
    --crit: #ff5c6c;   /* exploited */
    --good-bg: rgba(53,210,155,.13);
    --warn-bg: rgba(242,178,62,.14);
    --crit-bg: rgba(255,92,108,.14);
    --accent-bg: rgba(77,130,230,.14);
    --shadow: 0 1px 0 rgba(255,255,255,.02), 0 10px 26px -14px rgba(0,0,0,.65);
    --radius: 14px;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Code", Menlo, monospace;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #eef1f7; --panel: #ffffff; --panel-2: #f6f8fc;
      --line: #e0e6f0; --line-soft: #edf1f7;
      --fg: #141d2b; --muted: #59677e; --faint: #8492a9;
      --accent: #2968e6; --accent-solid: #2968e6; --accent-dim: #bcd0f5;
      --good: #12a06f; --warn: #c4881a; --crit: #d83b4c;
      --good-bg: rgba(18,160,111,.10); --warn-bg: rgba(196,136,26,.12); --crit-bg: rgba(216,59,76,.10);
      --accent-bg: rgba(41,104,230,.09);
      --shadow: 0 1px 2px rgba(16,32,56,.05), 0 14px 30px -18px rgba(16,32,56,.22);
    }
  }
  :root[data-theme="dark"] {
    --bg:#0b0f16; --panel:#121826; --panel-2:#0e1420; --line:#1e2637; --line-soft:#171f2d;
    --fg:#e7edf6; --muted:#8493ac; --faint:#58657e;
    --accent:#2968e6; --accent-solid:#2968e6; --accent-dim:#24457f;
    --good:#35d29b; --warn:#f2b23e; --crit:#ff5c6c;
    --good-bg:rgba(53,210,155,.13); --warn-bg:rgba(242,178,62,.14); --crit-bg:rgba(255,92,108,.14);
    --accent-bg:rgba(41,104,230,.14);
    --shadow:0 1px 0 rgba(255,255,255,.02),0 10px 26px -14px rgba(0,0,0,.65);
  }
  :root[data-theme="light"] {
    --bg:#eef1f7; --panel:#ffffff; --panel-2:#f6f8fc; --line:#e0e6f0; --line-soft:#edf1f7;
    --fg:#141d2b; --muted:#59677e; --faint:#8492a9;
    --accent:#2968e6; --accent-solid:#2968e6; --accent-dim:#bcd0f5;
    --good:#12a06f; --warn:#c4881a; --crit:#d83b4c;
    --good-bg:rgba(18,160,111,.10); --warn-bg:rgba(196,136,26,.12); --crit-bg:rgba(216,59,76,.10);
    --accent-bg:rgba(41,104,230,.09);
    --shadow:0 1px 2px rgba(16,32,56,.05),0 14px 30px -18px rgba(16,32,56,.22);
  }

  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg); font-family: var(--sans);
    -webkit-font-smoothing: antialiased; line-height: 1.5; }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 26px 22px 70px; }

  /* ---- page header ---- */
  .masthead { display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    margin-bottom: 6px; }
  .brandmark { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center;
    background: linear-gradient(150deg, var(--accent-solid), #1a3f8f); color: #fff;
    font-size: 15px; box-shadow: 0 4px 12px -4px var(--accent-solid); }
  .masthead h1 { font-size: 18px; letter-spacing: -.01em; margin: 0; font-weight: 650; }
  .masthead .sub { color: var(--muted); font-size: 13px; }
  .live { margin-left: auto; display: inline-flex; align-items: center; gap: 8px;
    font-size: 12px; color: var(--muted); font-family: var(--mono);
    padding: 5px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel); }
  .live .num { font-variant-numeric: tabular-nums; font-weight: 640; color: var(--fg); }
  .runstate { margin-left: auto; display: inline-flex; align-items: center; gap: 8px;
    font-size: 12px; font-family: var(--mono); font-weight: 600; letter-spacing: .02em;
    color: var(--accent); padding: 5px 11px; border: 1px solid var(--accent);
    border-radius: 999px; background: var(--accent-bg); }
  .runstate[hidden] { display: none; }
  .runstate .pulse { background: var(--accent); }
  .pulse { width: 7px; height: 7px; border-radius: 50%; background: var(--good);
    animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .25; } }
  @media (prefers-reduced-motion: reduce) { .pulse { animation: none; } }
  .note { color: var(--faint); font-size: 12px; margin: 12px 0 22px; font-family: var(--mono); }

  /* ---- the bento grid ---- */
  .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
  .w { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 16px 17px; display: flex; flex-direction: column;
    min-width: 0; position: relative; }
  .w > .whead { display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 13px; }
  .w .wt { font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
    font-family: var(--mono); display: flex; align-items: center; gap: 7px; }
  .w .wt .id { color: var(--accent); }
  .w .wtag { font-size: 10.5px; font-family: var(--mono); color: var(--faint);
    border: 1px solid var(--line); border-radius: 5px; padding: 1px 6px; }

  /* column spans */
  .c3 { grid-column: span 3; } .c4 { grid-column: span 4; } .c5 { grid-column: span 5; }
  .c6 { grid-column: span 6; } .c7 { grid-column: span 7; } .c8 { grid-column: span 8; }
  .c12 { grid-column: span 12; }
  @media (max-width: 900px) {
    .c3 { grid-column: span 6; } .c4,.c5 { grid-column: span 6; }
    .c6,.c7,.c8 { grid-column: span 12; }
  }
  @media (max-width: 560px) { .c3 { grid-column: span 12; } }

  /* ---- KPI stat widgets ---- */
  .kpi .val { font-size: 30px; font-weight: 650; font-family: var(--mono);
    font-variant-numeric: tabular-nums; letter-spacing: -.02em; line-height: 1; }
  .kpi .val small { font-size: 15px; color: inherit; font-weight: 500; }
  .kpi .delta { font-size: 11.5px; font-family: var(--mono); margin-top: 8px; color: var(--muted); }
  .kpi.good .val { color: var(--good); } .kpi.crit .val { color: var(--crit); }
  .up { color: var(--good); } .down { color: var(--crit); }
  .kpi .spark { margin-top: auto; padding-top: 10px; }

  /* ---- stacked pass/fail bars ---- */
  .rows { display: flex; flex-direction: column; gap: 11px; }
  .row .rhead { display: flex; justify-content: space-between; align-items: baseline;
    font-size: 12.5px; margin-bottom: 5px; }
  .row .rhead .cat { font-weight: 550; }
  .row .rhead .pct { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--muted); }
  .row .rhead .pct b { color: var(--fg); font-weight: 640; }
  .stack { display: flex; height: 10px; border-radius: 5px; overflow: hidden; background: var(--line-soft); }
  .stack i { display: block; height: 100%; }
  .stack .d { background: var(--good); } .stack .p { background: var(--warn); } .stack .e { background: var(--crit); }
  .legend { display: flex; gap: 16px; font-size: 11.5px; color: var(--muted); margin-top: 13px;
    padding-top: 12px; border-top: 1px solid var(--line-soft); }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .swatch { width: 9px; height: 9px; border-radius: 3px; display: inline-block; }

  /* ---- resilience trend ---- */
  .trend-num { font-family: var(--mono); font-variant-numeric: tabular-nums; display: flex;
    align-items: baseline; gap: 8px; margin-bottom: 6px; }
  .trend-num .num { font-size: 30px; font-weight: 650; }
  .trend-num .cap { color: var(--good); font-size: 12px; }
  .trend-sub { color: var(--muted); font-size: 11.5px; font-family: var(--mono); margin-top: 8px; }

  /* ---- owasp coverage ---- */
  .heat { display: grid; gap: 8px; }
  .heatrow { display: grid; grid-template-columns: 118px 1fr 34px; align-items: center; gap: 9px; font-size: 12px; }
  .heatrow .idc { font-family: var(--mono); color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .heatrow .idc b { color: var(--fg); }
  .bar { height: 8px; border-radius: 4px; background: var(--line-soft); overflow: hidden; }
  .bar i { display: block; height: 100%; background: linear-gradient(90deg, var(--accent-dim), var(--accent)); }
  .heatrow .cnt { font-family: var(--mono); font-variant-numeric: tabular-nums; text-align: right; color: var(--muted); }

  /* ---- finding lifecycle ---- */
  .pipe { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .stage { border: 1px solid var(--line); border-radius: 10px; padding: 12px 13px; background: var(--panel-2);
    display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
  .stage .nm { font-size: 11px; font-weight: 400; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .stage.open .nm { color: var(--crit); } .stage.prog .nm { color: var(--warn); } .stage.done .nm { color: var(--good); }
  .stage .cnt { font-size: 25px; font-weight: 650; font-family: var(--mono); line-height: 1; }
  .stage.open .cnt { color: var(--crit); }
  .stage.prog .cnt { color: var(--warn); }
  .stage.done .cnt { color: var(--good); }

  /* ---- chips / pills ---- */
  .pill { display: inline-flex; align-items: center; gap: 5px; font-family: var(--mono);
    font-size: 10.5px; padding: 2px 8px; border-radius: 999px; border: 1px solid transparent;
    font-weight: 600; letter-spacing: .02em; }
  .pill.def { color: var(--good); background: var(--good-bg); border-color: rgba(53,210,155,.3); }
  .pill.par { color: var(--warn); background: var(--warn-bg); border-color: rgba(242,178,62,.3); }
  .pill.exp { color: var(--crit); background: var(--crit-bg); border-color: rgba(255,92,108,.35); }
  .pill.neut { color: var(--muted); border-color: var(--line); }
  .sev { display: inline-block; width: 4px; height: 14px; border-radius: 2px; vertical-align: middle; }
  .sev.s-crit { background: var(--crit); } .sev.s-high { background: var(--warn); }
  .sev.s-med { background: var(--accent); } .sev.s-low { background: var(--faint); }
  .agentchip { font-family: var(--mono); font-size: 10.5px; padding: 2px 8px; border-radius: 6px;
    border: 1px solid var(--line); color: var(--muted); background: var(--panel-2); white-space: nowrap; }
  .agentchip.orc { color: #b98bff; border-color: rgba(185,139,255,.35); }
  .agentchip.red { color: var(--crit); border-color: rgba(255,92,108,.3); }
  .agentchip.jdg { color: var(--accent); border-color: rgba(41,104,230,.4); }
  .agentchip.adp { color: var(--good); border-color: rgba(53,210,155,.3); }
  .agentchip.opr { color: var(--muted); }

  /* ---- live agent feed ---- */
  .feed { font-family: var(--mono); font-size: 12px; }
  .feedrow { display: grid; grid-template-columns: 38px 86px 1fr auto; gap: 10px; align-items: center;
    padding: 8px 2px; border-bottom: 1px solid var(--line-soft); }
  .feedrow:last-child { border-bottom: 0; }
  .feedrow .seq { color: var(--faint); font-variant-numeric: tabular-nums; }
  .feedrow .cat { color: var(--fg); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .feedrow.fresh { background: linear-gradient(90deg, var(--good-bg), transparent); }

  /* ---- cost ---- */
  .costgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; }
  .costgrid .c .n { font-family: var(--mono); font-size: 21px; font-weight: 640; font-variant-numeric: tabular-nums; }
  .costgrid .c .l { font-size: 11px; color: var(--muted); margin-top: 2px; }
"""


_BODY = """
<div class="wrap">
  <div class="masthead">
    <span class="brandmark">◈</span>
    <h1>Agent Forge · Adversarial</h1>
    <span class="sub">live resilience console</span>
    <span class="runstate" id="runstate" hidden><span class="pulse"></span>run in progress</span>
    <span class="live" id="refresh-pill"><span class="pulse"></span>auto-refresh · <span class="num" id="refresh-count">5</span>s</span>
  </div>
  <div class="grid">

    <!-- KPI widgets -->
    <div class="w c3 kpi good">
      <div class="whead"><span class="wt"><span class="id">◆</span> Resilience</span></div>
      <div class="val" id="kpi-resilience">—</div>
      <div class="delta" id="kpi-resilience-sub">defended / attempts</div>
      <div class="spark">
        <svg viewBox="0 0 120 26" width="100%" height="26" preserveAspectRatio="none" aria-hidden="true">
          <polyline points="0,20 30,15 60,10 90,6 120,4" fill="none" stroke="var(--good)" stroke-width="2"/>
        </svg>
      </div>
    </div>
    <div class="w c3 kpi">
      <div class="whead"><span class="wt">Attempts</span></div>
      <div class="val" id="kpi-attempts">—</div>
      <div class="delta" id="kpi-attempts-sub">across categories</div>
    </div>
    <div class="w c3 kpi crit">
      <div class="whead"><span class="wt">Exploits</span></div>
      <div class="val" id="kpi-exploits">—</div>
      <div class="delta down" id="kpi-exploits-sub">open findings</div>
    </div>
    <div class="w c3 kpi">
      <div class="whead"><span class="wt">Cost / run</span></div>
      <div class="val" id="kpi-cost">—</div>
      <div class="delta" id="kpi-cost-sub">per attempt</div>
    </div>

    <!-- pass/fail by category -->
    <div class="w c6">
      <div class="whead"><span class="wt"><span class="id">01</span> Pass / fail by category</span><span class="wtag">pass_fail()</span></div>
      <div class="rows" id="passfail-rows"></div>
      <div class="legend" id="passfail-legend"></div>
    </div>

    <!-- resilience trend -->
    <div class="w c6">
      <div class="whead"><span class="wt"><span class="id">02</span> Resilience trend</span><span class="wtag">resilience_trend()</span></div>
      <div class="trend-num"><span class="num" id="trend-num">—</span><span class="cap" id="trend-cap"></span></div>
      <svg viewBox="0 0 320 96" width="100%" preserveAspectRatio="none" role="img" aria-label="Resilience trend over target versions">
        <defs>
          <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--accent)" stop-opacity=".34"/>
            <stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <line x1="0" y1="80" x2="320" y2="80" stroke="var(--line)" stroke-width="1"/>
        <path id="trend-area" d="" fill="url(#fill)"/>
        <path id="trend-line" d="" fill="none" stroke="var(--accent)" stroke-width="2.5"/>
        <circle id="trend-dot" cx="320" cy="14" r="4.5" fill="var(--accent)"/>
        <circle id="trend-halo" cx="320" cy="14" r="9" fill="var(--accent)" opacity=".18"/>
      </svg>
      <div class="trend-sub" id="trend-sub"></div>
    </div>

    <!-- owasp coverage -->
    <div class="w c6">
      <div class="whead"><span class="wt"><span class="id">03</span> OWASP coverage</span><span class="wtag">coverage()</span></div>
      <div class="heat" id="owasp-heat"></div>
    </div>

    <!-- cost -->
    <div class="w c3">
      <div class="whead"><span class="wt"><span class="id">04</span> Cost</span><span class="wtag">cost()</span></div>
      <div class="costgrid" id="cost-grid"></div>
    </div>

    <!-- finding lifecycle -->
    <div class="w c3">
      <div class="whead"><span class="wt"><span class="id">05</span> Findings</span><span class="wtag">outcomes()</span></div>
      <div class="pipe" id="findings-pipe"></div>
    </div>

    <!-- live agent feed (wide) -->
    <div class="w c12">
      <div class="whead">
        <span class="wt"><span class="id">06</span> Live agent activity</span>
        <span style="display:flex; gap:7px; flex-wrap:wrap">
          <span class="agentchip orc">orchestrator</span><span class="agentchip red">red_team</span>
          <span class="agentchip jdg">judge</span><span class="agentchip adp">adapter</span>
        </span>
      </div>
      <div class="feed" id="agent-feed"></div>
    </div>

  </div>
</div>
"""


_SCRIPT = r"""
(function () {
  var lastSeq = null;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function pct(x) { return Math.round((Number(x) || 0) * 100); }
  function usd(x) { return "$" + (Number(x) || 0).toFixed(2); }
  function kfmt(n) {
    n = Number(n) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(n);
  }

  var AGENT_CLASS = {
    orchestrator: "orc", red_team: "red", judge: "jdg", adapter: "adp", operator: "opr"
  };
  var VERDICT_PILL = {
    success: ["exp", "exploited"], fail: ["def", "defended"], partial: ["par", "partial"]
  };

  function renderKpis(k) {
    document.getElementById("kpi-resilience").innerHTML =
      pct(k.resilience) + '<small>%</small>';
    document.getElementById("kpi-attempts").textContent = k.attempts;
    document.getElementById("kpi-exploits").textContent = k.exploits;
    document.getElementById("kpi-cost").innerHTML =
      '<small>$</small>' + (Number(k.total_usd) || 0).toFixed(2);
    document.getElementById("kpi-cost-sub").textContent =
      usd(k.usd_per_attempt) + " / attempt";
    document.getElementById("kpi-exploits-sub").textContent =
      k.exploits + (k.exploits === 1 ? " exploit" : " exploits");
  }

  function renderPassFail(pf) {
    var byCat = pf.by_category || {};
    var rows = "";
    var td = 0, tp = 0, te = 0;
    Object.keys(byCat).forEach(function (cat) {
      var b = byCat[cat];
      var a = b.attempts || 0;
      td += b.defended || 0; tp += b.partial || 0; te += b.exploits || 0;
      var dw = a ? (100 * (b.defended || 0) / a) : 0;
      var pw = a ? (100 * (b.partial || 0) / a) : 0;
      var ew = a ? (100 * (b.exploits || 0) / a) : 0;
      rows +=
        '<div class="row"><div class="rhead"><span class="cat">' + esc(cat) +
        '</span><span class="pct"><b>' + pct(b.pass_rate) + '%</b> · ' + a +
        '</span></div><div class="stack">' +
        '<i class="d" style="width:' + dw + '%"></i>' +
        '<i class="p" style="width:' + pw + '%"></i>' +
        '<i class="e" style="width:' + ew + '%"></i></div></div>';
    });
    document.getElementById("passfail-rows").innerHTML = rows;
    document.getElementById("passfail-legend").innerHTML =
      '<span style="color:var(--good)"><i class="swatch" style="background:var(--good)"></i> Defended ' + td + '</span>' +
      '<span style="color:var(--warn)"><i class="swatch" style="background:var(--warn)"></i> Partial ' + tp + '</span>' +
      '<span style="color:var(--crit)"><i class="swatch" style="background:var(--crit)"></i> Exploited ' + te + '</span>';
  }

  function renderTrend(trend) {
    trend = trend || [];
    var n = trend.length;
    var num = document.getElementById("trend-num");
    var sub = document.getElementById("trend-sub");
    var cap = document.getElementById("trend-cap");
    if (!n) {
      num.textContent = "—"; sub.textContent = ""; cap.textContent = "";
      document.getElementById("trend-area").setAttribute("d", "");
      document.getElementById("trend-line").setAttribute("d", "");
      return;
    }
    var W = 320, H = 80;
    var pts = trend.map(function (p, i) {
      var x = n === 1 ? W : (i / (n - 1)) * W;
      var y = H - (Number(p.pass_rate) || 0) * (H - 8);
      return [x, y];
    });
    var line = pts.map(function (p, i) {
      return (i ? "L" : "M") + p[0].toFixed(0) + "," + p[1].toFixed(0);
    }).join(" ");
    var area = line + " L" + W + "," + H + " L0," + H + " Z";
    document.getElementById("trend-line").setAttribute("d", line);
    document.getElementById("trend-area").setAttribute("d", area);
    var last = pts[n - 1];
    document.getElementById("trend-dot").setAttribute("cx", last[0].toFixed(0));
    document.getElementById("trend-dot").setAttribute("cy", last[1].toFixed(0));
    document.getElementById("trend-halo").setAttribute("cx", last[0].toFixed(0));
    document.getElementById("trend-halo").setAttribute("cy", last[1].toFixed(0));
    num.textContent = pct(trend[n - 1].pass_rate) + "%";
    var delta = pct(trend[n - 1].pass_rate) - pct(trend[0].pass_rate);
    cap.textContent = (delta >= 0 ? "▲ +" : "▼ ") + delta + " pts";
    sub.textContent = trend.map(function (p) {
      return esc(p.version == null ? "?" : p.version) + " " + pct(p.pass_rate);
    }).join(" · ");
  }

  function renderOwasp(coverage) {
    var byOwasp = (coverage && coverage.by_owasp) || {};
    var entries = Object.keys(byOwasp).map(function (k) { return [k, byOwasp[k]]; });
    entries.sort(function (a, b) { return b[1] - a[1]; });
    var max = entries.reduce(function (m, e) { return Math.max(m, e[1]); }, 0) || 1;
    document.getElementById("owasp-heat").innerHTML = entries.map(function (e) {
      var id = e[0], cnt = e[1];
      var label = String(id).split(":")[0];
      return '<div class="heatrow"><span class="idc"><b>' + esc(label) + '</b> ' +
        esc(String(id).replace(/^[^:]*:?/, "")) + '</span>' +
        '<span class="bar"><i style="width:' + (100 * cnt / max) + '%"></i></span>' +
        '<span class="cnt">' + cnt + '</span></div>';
    }).join("");
  }

  function renderCost(cost) {
    cost = cost || {};
    document.getElementById("cost-grid").innerHTML =
      '<div class="c"><div class="n">' + usd(cost.total_usd) + '</div><div class="l">total this run</div></div>' +
      '<div class="c"><div class="n">$' + (Number(cost.usd_per_attempt) || 0).toFixed(3) + '</div><div class="l">per attempt</div></div>' +
      '<div class="c"><div class="n">' + kfmt(cost.total_input_tokens) + '</div><div class="l">input tokens</div></div>' +
      '<div class="c"><div class="n">' + kfmt(cost.total_output_tokens) + '</div><div class="l">output tokens</div></div>';
  }

  function renderFindings(o) {
    o = o || {};
    // verdict outcomes: exploited (crit) / partial (warn) / defended (good)
    document.getElementById("findings-pipe").innerHTML =
      '<div class="stage open"><div class="nm">Exploited</div><div class="cnt">' + (o.exploited || 0) + '</div></div>' +
      '<div class="stage prog"><div class="nm">Partial</div><div class="cnt">' + (o.partial || 0) + '</div></div>' +
      '<div class="stage done"><div class="nm">Defended</div><div class="cnt">' + (o.defended || 0) + '</div></div>';
  }

  function renderFeed(activity, verdicts) {
    activity = (activity || []).slice();
    activity.sort(function (a, b) { return (b.seq || 0) - (a.seq || 0); });
    var top = activity.slice(0, 8);
    var newest = top.length ? top[0].seq : null;
    var fresh = (newest !== null && newest !== lastSeq);
    document.getElementById("agent-feed").innerHTML = top.map(function (ev, i) {
      var cls = AGENT_CLASS[ev.agent] || "opr";
      var label = esc(ev.kind) + (ev.category ? " · " + esc(ev.category) : "");
      var pill = "";
      if (ev.kind === "verdict") {
        var v = verdicts[ev.seq];
        var vp = VERDICT_PILL[v];
        if (vp) pill = '<span class="pill ' + vp[0] + '">' + vp[1] + '</span>';
      }
      return '<div class="feedrow' + (i === 0 && fresh ? ' fresh' : '') + '">' +
        '<span class="seq">#' + esc(ev.seq) + '</span>' +
        '<span class="agentchip ' + cls + '">' + esc(ev.agent) + '</span>' +
        '<span class="cat">' + label + '</span>' + (pill || '<span></span>') + '</div>';
    }).join("");
    if (newest !== null) lastSeq = newest;
  }

  function renderRunState(active) {
    var el = document.getElementById("runstate");
    if (el) el.hidden = !active;
  }

  function render(state) {
    if (!state) return;
    render.state = state;
    renderKpis(state.kpis || {});
    renderPassFail(state.pass_fail || {});
    renderTrend(state.resilience_trend || []);
    renderOwasp(state.coverage || {});
    renderCost(state.cost || {});
    renderFindings(state.outcomes || {});
    renderFeed(state.agent_activity || [], state.verdicts || {});
    renderRunState(!!state.run_active);
  }

  // countdown: update ONLY the number so the green pulse dot + "auto-refresh"
  // label stay put; poll at zero, then reset to 5.
  var REFRESH_S = 5, left = REFRESH_S, polling = false;
  function paintCount() {
    var el = document.getElementById("refresh-count");
    if (el) el.textContent = left;
  }
  function poll() {
    if (polling) return;
    polling = true;
    return fetch("/api/state", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {})
      .then(function () { polling = false; });
  }
  function tick() {
    if (polling) return;
    left -= 1;
    if (left <= 0) { poll(); left = REFRESH_S; }
    paintCount();
  }

  var initial = null;
  try {
    initial = JSON.parse(document.getElementById("initial-state").textContent);
  } catch (e) { initial = null; }
  render(initial);
  paintCount();
  setInterval(tick, 1000);
})();
"""


def render_html(state: dict) -> str:
    """Render ONE self-contained, data-driven HTML document for ``state``."""
    payload = json.dumps(state).replace("</", "<\\/")
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Agent Forge · Adversarial — live resilience console</title>\n"
        "<style>" + _STYLE + "</style>\n"
        "</head>\n"
        "<body>\n"
        + _BODY
        + '<script id="initial-state" type="application/json">'
        + payload
        + "</script>\n"
        + "<script>" + _SCRIPT + "</script>\n"
        + "</body>\n</html>\n"
    )


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #
def handle_path(path, state_provider):
    """Pure router. ``state_provider`` is called fresh for every request."""
    clean = path.split("?", 1)[0]
    if clean in ("/", "/index.html"):
        return (200, "text/html; charset=utf-8", render_html(state_provider()))
    if clean == "/api/state":
        return (200, "application/json", json.dumps(state_provider()))
    if clean == "/health":
        return (200, "application/json", json.dumps({"status": "ok"}))
    return (404, "text/plain; charset=utf-8", "not found")


# --------------------------------------------------------------------------- #
# server
# --------------------------------------------------------------------------- #
def make_server(store, *, host="0.0.0.0", port=8000, cases=None):
    """A bound ThreadingHTTPServer serving the live dashboard over ``store``."""

    def state_provider():
        return build_state(Observability(store, cases=cases))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status, ctype, body = handle_path(self.path, state_provider)
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args, **kwargs):  # silence default logging
            pass

    return ThreadingHTTPServer((host, port), Handler)


def serve(store, *, host="0.0.0.0", port=8000, cases=None):
    """Start the dashboard server and block, serving forever."""
    server = make_server(store, host=host, port=port, cases=cases)
    server.serve_forever()


def resolve_bind(args, env):
    """Resolve (host, port): explicit --port > PORT env (Railway) > 8000."""
    if getattr(args, "port", None) is not None:
        port = int(args.port)
    elif env.get("PORT"):
        port = int(env["PORT"])
    else:
        port = 8000
    host = getattr(args, "host", None) or "0.0.0.0"
    return host, port
