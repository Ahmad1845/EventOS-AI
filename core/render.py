"""Render module: terminal summary, out/final_plan.json, out/trace.txt, out/session_trace.txt, and out/report.html per Section 19."""

import html
import json
import os
from typing import Any, Dict, List


OUT_DIR = "out"


def format_terminal_output(
    trace_text: str,
    plan: Dict[str, Any],
    state: Dict[str, Any],
    run_tokens: int,
) -> str:
    """
    Format terminal output per Section 19.2:
    1. Trace (as in section 10)
    2. Plan summary: five labelled sections with key figures
    3. Checks table (six official checks with pass or fail)
    4. Rejected or excluded messages with reasons
    5. Final TOTAL TOKENS line (last line of the run)
    """
    lines: List[str] = []
    lines.append(trace_text)
    lines.append("")

    hc = plan.get("headcount") or {}
    venue = plan.get("venue") or {}
    sched = plan.get("schedule") or {}
    food = plan.get("food") or {}
    judging = plan.get("judging") or {}
    budget = plan.get("budget") or {}

    lines.append(
        f"=== PLAN SUMMARY (v{plan.get('version', 1)} | valid={plan.get('valid', False)} | "
        f"headcount={hc.get('total', 0)}: {hc.get('students', 0)} students + "
        f"{hc.get('staff', 0)} staff + {hc.get('judges', 0)} judges) ==="
    )

    # 1. VENUE
    lines.append(
        f"[1. VENUE]    {venue.get('name')} | capacity={venue.get('capacity')} "
        f"(slack={venue.get('slack')}) | price=Rs {venue.get('price')}"
    )
    for r in venue.get("rejected_options") or []:
        lines.append(f"              - rejected {r.get('name')}: {r.get('reason')}")
    for sf in venue.get("skipped_fitting") or []:
        lines.append(f"              - skipped {sf.get('name')}: {sf.get('reason')}")

    # 2. SCHEDULE
    blocks = sched.get("blocks") or []
    block_strs = [
        f"{b.get('name')} ({b.get('start')}-{b.get('end')}m: {b.get('minutes')}m)"
        for b in blocks
    ]
    lines.append(
        f"[2. SCHEDULE] duration={sched.get('duration_minutes')} min | "
        + " -> ".join(block_strs)
    )

    # 3. FOOD
    lines.append(
        f"[3. FOOD]     option={food.get('option')} | quantity={food.get('quantity')} | "
        f"unit_price=Rs {food.get('unit_price')} | delivery=Rs {food.get('delivery_fee')} | "
        f"cost=Rs {food.get('cost')}"
    )

    # 4. JUDGING
    lines.append(
        f"[4. JUDGING]  teams={judging.get('teams')} | required={judging.get('required')} | "
        f"engaged={judging.get('engaged')} (confirmed={judging.get('confirmed')}) | "
        f"window={judging.get('window_minutes')} min | honorarium=Rs {judging.get('honorarium_total')}"
    )

    # 5. BUDGET
    lines.append(
        f"[5. BUDGET]   total=Rs {budget.get('total')} | cap=Rs {budget.get('cap')} | "
        f"remaining=Rs {budget.get('remaining')}"
    )
    for item in budget.get("items") or []:
        lines.append(
            f"              - {item.get('label')}: Rs {item.get('amount')} (msg {item.get('source_message')})"
        )

    lines.append("")
    lines.append("=== SIX OFFICIAL CHECKS ===")
    official_ids = {"figures", "budget", "venue_fit", "schedule", "judges", "coverage"}
    for chk in plan.get("checks") or []:
        cid = str(chk.get("id", ""))
        status_str = "PASS" if chk.get("passed") else "FAIL"
        tag = "[OFFICIAL]" if cid in official_ids else "[GUARD]   "
        lines.append(f"  {status_str}  {tag} {cid.ljust(12)} | {chk.get('detail', '')}")

    lines.append("")
    lines.append("=== REJECTED, EXCLUDED & IGNORED MESSAGES ===")
    rejections = plan.get("rejections") or []
    excluded = plan.get("excluded_requests") or []
    ignored_msgs = [
        m for m in (state.get("messages") or []) if m.get("status") == "ignored"
    ]

    if not rejections and not excluded and not ignored_msgs:
        lines.append("  None")
    else:
        for rej in rejections:
            lines.append(
                f"  [REJECTED] msg {rej.get('seq')} ({rej.get('sender')}): "
                f"[{rej.get('check')}] {rej.get('reason')}"
            )
        for ex in excluded:
            lines.append(
                f"  [EXCLUDED] {ex.get('item')} (Rs {ex.get('amount')}): {ex.get('reason')}"
            )
        for ig in ignored_msgs:
            meta = ig.get("meta") or {}
            lines.append(
                f"  [IGNORED]  msg {ig.get('seq')} ({meta.get('sender', 'Unknown')}): "
                f"{meta.get('reason', 'irrelevant')}"
            )

    lines.append("")
    lines.append(f"TOTAL TOKENS: {run_tokens}")
    return "\n".join(lines)


def _esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""))


def generate_html_report(
    plan: Dict[str, Any],
    state: Dict[str, Any],
    last_mode: str,
) -> str:
    """Generate self-contained static out/report.html per Section 19.3."""
    valid = bool(plan.get("valid", False))
    badge_bg = "seagreen" if valid else "firebrick"
    badge_text = "VALID PLAN" if valid else "INVALID PLAN"

    hc = plan.get("headcount") or {}
    venue = plan.get("venue") or {}
    sched = plan.get("schedule") or {}
    food = plan.get("food") or {}
    judging = plan.get("judging") or {}
    budget = plan.get("budget") or {}
    tokens = plan.get("tokens") or {"last_run": 0, "session": 0}
    recomputed = plan.get("recomputed_areas") or []
    all_areas = ["judging", "venue", "food", "schedule", "budget"]
    reused = [a for a in all_areas if a not in recomputed]

    cap = int(budget.get("cap") or 1)
    total_spent = int(budget.get("total") or 0)
    pct = min(10 ** 2, max(0, int(round((total_spent / cap) * (10 ** 2))))) if cap > 0 else 0
    meter_color = "seagreen" if total_spent <= cap else "firebrick"

    # Build schedule timeline blocks
    sched_dur = max(1, int(sched.get("duration_minutes") or 1))
    sched_rows_html = []
    for b in sched.get("blocks") or []:
        mins = int(b.get("minutes") or 0)
        w_pct = max(6, int(round((mins / sched_dur) * (10 ** 2))))
        clk = (
            f" ({_esc(b.get('clock_start'))}–{_esc(b.get('clock_end'))})"
            if b.get("clock_start")
            else ""
        )
        sched_rows_html.append(
            f"<div class='t-block' style='flex:{w_pct}'>"
            f"<div class='t-name'>{_esc(b.get('name'))}</div>"
            f"<div class='t-meta'>{mins}m | {b.get('start')}–{b.get('end')}m{clk}</div>"
            f"</div>"
        )

    # Budget items rows
    budget_rows_html = []
    for item in budget.get("items") or []:
        budget_rows_html.append(
            f"<tr>"
            f"<td>{_esc(item.get('label'))}</td>"
            f"<td>Msg #{_esc(item.get('source_message'))}</td>"
            f"<td class='num'>Rs {int(item.get('amount', 0)):,}</td>"
            f"</tr>"
        )

    # Venue rejected and skipped-fitting options
    venue_rej_html = []
    for r in venue.get("rejected_options") or []:
        venue_rej_html.append(
            f"<li><strong>{_esc(r.get('name'))}</strong> (seats {_esc(r.get('capacity'))}, Rs {_esc(r.get('price'))}): "
            f"<span class='muted'>{_esc(r.get('reason'))}</span></li>"
        )
    for sf in venue.get("skipped_fitting") or []:
        venue_rej_html.append(
            f"<li><strong>{_esc(sf.get('name'))}</strong> (seats {_esc(sf.get('capacity'))}, Rs {_esc(sf.get('price'))}): "
            f"<span class='muted'>{_esc(sf.get('reason'))}</span></li>"
        )

    # Judging assignments preview
    assignments = judging.get("assignments") or []
    assign_items = []
    for a in assignments:
        t_list = ", ".join(f"T{t}" for t in (a.get("teams") or []))
        assign_items.append(
            f"<span class='chip'>Judge {_esc(a.get('judge'))}: [{_esc(t_list)}]</span>"
        )

    # Checks panel
    checks_html = []
    for chk in plan.get("checks") or []:
        passed = bool(chk.get("passed"))
        cls = "chk-pass" if passed else "chk-fail"
        mark = "PASS" if passed else "FAIL"
        checks_html.append(
            f"<div class='chk-card {cls}'>"
            f"<div class='chk-head'><span class='chk-mark'>{mark}</span> <strong>{_esc(chk.get('id'))}</strong></div>"
            f"<div class='chk-detail'>{_esc(chk.get('detail'))}</div>"
            f"</div>"
        )

    # Rejected, excluded, ignored messages
    rej_cards_html = []
    for rej in plan.get("rejections") or []:
        rej_cards_html.append(
            f"<div class='msg-card msg-reject'>"
            f"<div><strong>REJECTED — Message #{_esc(rej.get('seq'))} ({_esc(rej.get('sender'))})</strong> "
            f"| Failed check: <code>{_esc(rej.get('check'))}</code></div>"
            f"<div class='msg-reason'>{_esc(rej.get('reason'))}</div>"
            f"<div class='msg-text'>{_esc(rej.get('text', ''))}</div>"
            f"</div>"
        )
    for ex in plan.get("excluded_requests") or []:
        rej_cards_html.append(
            f"<div class='msg-card msg-warn'>"
            f"<div><strong>EXCLUDED REQUEST — {_esc(ex.get('item'))} (Rs {int(ex.get('amount', 0)):,})</strong></div>"
            f"<div class='msg-reason'>Reason: {_esc(ex.get('reason'))}</div>"
            f"</div>"
        )
    for m in state.get("messages") or []:
        if m.get("status") == "ignored":
            meta = m.get("meta") or {}
            rej_cards_html.append(
                f"<div class='msg-card msg-warn'>"
                f"<div><strong>IGNORED — Message #{_esc(m.get('seq'))} ({_esc(meta.get('sender'))})</strong></div>"
                f"<div class='msg-reason'>Reason: {_esc(meta.get('reason'))}</div>"
                f"<div class='msg-text'>{_esc(m.get('text'))}</div>"
                f"</div>"
            )
    if not rej_cards_html:
        rej_cards_html.append("<p class='muted'>No rejected, excluded, or ignored messages.</p>")

    # Trace panel (all runs in state.trace_history)
    trace_blocks_html = []
    for run_tr in state.get("trace_history") or []:
        r_num = run_tr.get("run_number")
        r_mode = run_tr.get("mode")
        r_file = run_tr.get("filename")
        r_tok = run_tr.get("total_tokens", 0)
        inner_items = []
        for entry in run_tr.get("entries") or []:
            if entry.get("kind") == "model_call":
                tok_line = (
                    f"input={entry.get('input_tokens')} output={entry.get('output_tokens')} total={entry.get('total_tokens')}"
                    if entry.get("reported")
                    else "not reported"
                )
                inner_items.append(
                    f"<details class='mc-box' open>"
                    f"<summary><strong>MODEL CALL {_esc(entry.get('n'))}</strong> | "
                    f"model: <code>{_esc(entry.get('model'))}</code> | "
                    f"area: <code>{_esc(entry.get('area'))}</code> | "
                    f"tokens: <code>{_esc(tok_line)}</code></summary>"
                    f"<div class='mc-body'>"
                    f"<div><strong>Input:</strong><pre>{_esc(entry.get('input'))}</pre></div>"
                    f"<div><strong>Output:</strong><pre>{_esc(entry.get('output'))}</pre></div>"
                    f"</div></details>"
                )
            else:
                inner_items.append(
                    f"<div class='py-line'><code>PYTHON | {_esc(entry.get('stage', '').ljust(9))} | {_esc(entry.get('text'))}</code></div>"
                )
        trace_blocks_html.append(
            f"<div class='run-box'>"
            f"<div class='run-head'>RUN #{_esc(r_num)} ({_esc(r_mode)}) — File: <code>{_esc(r_file)}</code> — Run Tokens: <strong>{_esc(r_tok)}</strong></div>"
            f"{''.join(inner_items)}"
            f"</div>"
        )

    slip_text = (
        f"Model calls will be: reading (1 call). "
        f"Python-only recompute: {', '.join(recomputed) if recomputed else 'none (plan unchanged)'}."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>EventOS Report — MTM Hackathon Planner</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #f8fafc; color: midnightblue; margin: 0; padding: 24px; line-height: 1.5; }}
  .container {{ max-width: 84rem; margin: 0 auto; }}
  .header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; background: #ffffff; border: 1px solid #cbd5e1; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }}
  .title {{ font-size: 20px; font-weight: bold; margin: 0; }}
  .meta-bar {{ display: flex; gap: 16px; align-items: center; font-size: 13px; font-family: monospace; }}
  .badge {{ color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; background: {badge_bg}; }}
  .grid-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr)); gap: 16px; margin-bottom: 16px; }}
  .card {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; }}
  .card h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.04em; color: darkslategray; margin: 0 0 10px 0; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
  .stat-big {{ font-size: 22px; font-weight: bold; font-family: monospace; margin-bottom: 6px; }}
  .muted {{ color: slategray; font-size: 13px; }}
  .timeline {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }}
  .t-block {{ background: #f1f5f9; border: 1px solid #94a3b8; border-radius: 4px; padding: 8px; min-width: 6rem; }}
  .t-name {{ font-weight: bold; font-size: 13px; }}
  .t-meta {{ font-size: 11px; font-family: monospace; color: darkslategray; }}
  table {{ width: calc(50% + 50%); border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
  th, td {{ border-bottom: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }}
  td.num, th.num {{ text-align: right; font-family: monospace; }}
  .meter-wrap {{ background: #e2e8f0; height: 10px; border-radius: 5px; overflow: hidden; margin: 8px 0; }}
  .meter-bar {{ height: 10px; background: {meter_color}; width: {pct}%; }}
  .checks-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 10px; }}
  .chk-card {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; background: #ffffff; }}
  .chk-pass {{ border-color: seagreen; background: #f0fdf4; }}
  .chk-fail {{ border-color: firebrick; background: #fef2f2; }}
  .chk-mark {{ font-family: monospace; font-weight: bold; font-size: 12px; padding: 2px 6px; border-radius: 3px; color: white; background: seagreen; }}
  .chk-fail .chk-mark {{ background: firebrick; }}
  .chk-detail {{ font-size: 12px; font-family: monospace; margin-top: 6px; color: darkslategray; }}
  .msg-card {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; margin-bottom: 10px; }}
  .msg-reject {{ border-color: firebrick; background: #fef2f2; }}
  .msg-warn {{ border-color: goldenrod; background: #fffbeb; }}
  .msg-reason {{ font-family: monospace; font-size: 13px; margin-top: 4px; color: midnightblue; }}
  .msg-text {{ font-size: 12px; color: dimgray; margin-top: 4px; font-style: italic; }}
  .chip-wrap {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
  .chip {{ font-family: monospace; font-size: 11px; background: #f1f5f9; border: 1px solid #cbd5e1; padding: 2px 6px; border-radius: 4px; }}
  .run-box {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; margin-bottom: 12px; background: #f8fafc; }}
  .run-head {{ font-weight: bold; margin-bottom: 8px; font-size: 14px; }}
  .mc-box {{ background: #ffffff; border: 1px solid #94a3b8; border-radius: 4px; padding: 8px; margin-bottom: 8px; }}
  .mc-body pre {{ background: midnightblue; color: #f8fafc; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 12px; white-space: pre-wrap; }}
  .py-line {{ font-size: 12px; padding: 2px 0; color: darkslategray; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1 class="title">EventOS — Mind to Machine Hackathon Plan &amp; Trace</h1>
      <div class="muted">Headcount: <strong>{_esc(hc.get('total'))}</strong> ({_esc(hc.get('students'))} students + {_esc(hc.get('staff'))} staff + {_esc(hc.get('judges'))} judges)</div>
    </div>
    <div class="meta-bar">
      <span class="badge">{badge_text}</span>
      <span>Version: <strong>v{_esc(plan.get('version'))}</strong></span>
      <span>Mode: <strong>{_esc(last_mode)}</strong></span>
      <span>Run Tokens: <strong>{_esc(tokens.get('last_run'))}</strong></span>
      <span>Session Tokens: <strong>{_esc(tokens.get('session'))}</strong></span>
    </div>
  </div>

  <div class="grid-cards">
    <div class="card">
      <h2>1. Venue</h2>
      <div class="stat-big">{_esc(venue.get('name') or 'None')} — Rs {int(venue.get('price', 0)):,}</div>
      <div>Capacity: <strong>{_esc(venue.get('capacity'))} seats</strong> (Headcount: {_esc(hc.get('total'))}, Slack: +{_esc(venue.get('slack'))} seats)</div>
      <div class="muted">Features: {_esc(', '.join(venue.get('features') or []) or 'Standard')}</div>
      <ul class="muted" style="padding-left:18px; margin-top:8px;">{''.join(venue_rej_html)}</ul>
    </div>

    <div class="card">
      <h2>2. Food &amp; Catering</h2>
      <div class="stat-big">{_esc(food.get('name') or food.get('option'))} — Rs {int(food.get('cost', 0)):,}</div>
      <div>Quantity: <strong>{_esc(food.get('quantity'))} boxes</strong> &times; Rs {int(food.get('unit_price', 0)):,}/head</div>
      <div class="muted">Delivery fee: Rs {int(food.get('delivery_fee', 0)):,}</div>
    </div>

    <div class="card">
      <h2>3. Judging</h2>
      <div class="stat-big">{_esc(judging.get('engaged'))} Judges Engaged — Rs {int(judging.get('honorarium_total', 0)):,}</div>
      <div>Teams: <strong>{_esc(judging.get('teams'))}</strong> | Required: <strong>{_esc(judging.get('required'))}</strong> | Confirmed: <strong>{_esc(judging.get('confirmed'))}</strong></div>
      <div>Judging Window: <strong>{_esc(judging.get('window_minutes'))} min</strong> ({_esc(judging.get('minutes_per_team'))} min/team, max {_esc(judging.get('max_teams_per_judge'))} teams/judge)</div>
      <div class="chip-wrap">{''.join(assign_items)}</div>
    </div>

    <div class="card">
      <h2>4. Budget &amp; Cap Meter</h2>
      <div class="stat-big">Rs {total_spent:,} / Rs {cap:,}</div>
      <div>Remaining Balance: <strong>Rs {int(budget.get('remaining', 0)):,}</strong> ({pct}% used)</div>
      <div class="meter-wrap"><div class="meter-bar"></div></div>
      <table>
        <thead><tr><th>Line Item</th><th>Source</th><th class="num">Amount</th></tr></thead>
        <tbody>{''.join(budget_rows_html)}</tbody>
      </table>
    </div>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h2>5. Schedule Timeline ({_esc(sched.get('duration_minutes'))} Minutes Total)</h2>
    <div class="timeline">{''.join(sched_rows_html)}</div>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h2>Validation Checks (6 Official Checks + Constraints &amp; Floors)</h2>
    <div class="checks-grid">{''.join(checks_html)}</div>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h2>Change &amp; Router Panel (Prediction Slip)</h2>
    <div><strong>Recomputed Areas:</strong> <code>{_esc(', '.join(recomputed) if recomputed else 'none')}</code> | <strong>Reused Areas:</strong> <code>{_esc(', '.join(reused) if reused else 'none')}</code></div>
    <div style="margin-top:6px;"><strong>Prediction Slip Text:</strong> <code>{_esc(slip_text)}</code></div>
  </div>

  <div class="card" style="margin-bottom:16px;">
    <h2>Rejected, Excluded &amp; Ignored Messages</h2>
    {''.join(rej_cards_html)}
  </div>

  <div class="card">
    <h2>Execution Trace &amp; Token Accounting (Session Total: {_esc(tokens.get('session'))} Tokens)</h2>
    {''.join(trace_blocks_html)}
  </div>
</div>
</body>
</html>"""


def write_outputs(
    plan: Dict[str, Any],
    state: Dict[str, Any],
    run_trace_text: str,
    last_mode: str,
    out_dir: str = OUT_DIR,
) -> str:
    """Write out/final_plan.json, out/trace.txt, out/session_trace.txt, out/report.html and return terminal output."""
    os.makedirs(out_dir, exist_ok=True)

    plan_path = os.path.join(out_dir, "final_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    trace_path = os.path.join(out_dir, "trace.txt")
    with open(trace_path, "w", encoding="utf-8") as f:
        f.write(run_trace_text + "\n")

    # Build session_trace.txt from all runs in state.trace_history
    session_blocks: List[str] = []
    for rt in state.get("trace_history") or []:
        if rt.get("formatted"):
            session_blocks.append(str(rt["formatted"]))
    session_total = int(state.get("session_tokens", 0))
    session_blocks.append(f"SESSION TOTAL TOKENS: {session_total}")
    session_blocks.append(f"TOTAL TOKENS: {session_total}")
    session_trace_path = os.path.join(out_dir, "session_trace.txt")
    with open(session_trace_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(session_blocks) + "\n")

    html_content = generate_html_report(plan, state, last_mode=last_mode)
    report_path = os.path.join(out_dir, "report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    run_tokens = int((plan.get("tokens") or {}).get("last_run", 0))
    return format_terminal_output(run_trace_text, plan, state, run_tokens=run_tokens)
