"""Schedule solver per Section 15.5."""

import math
from typing import Any, Dict, List, Optional


def _parse_hhmm(clock_str: Optional[str]) -> Optional[int]:
    if not clock_str or not isinstance(clock_str, str) or ":" not in clock_str:
        return None
    try:
        parts = clock_str.strip().split(":")
        h = int(parts[0])
        m = int(parts[1])
        return h * 60 + m
    except Exception:
        return None


def _format_hhmm(total_minutes: int) -> str:
    day_mins = 24 * 60
    m_norm = total_minutes % day_mins
    h = m_norm // 60
    m = m_norm % 60
    return f"{h:02d}:{m:02d}"


def _humanize_block(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("_", " ").split())


def solve_schedule(
    winning_facts: Dict[str, Any],
    constraints: List[Dict[str, Any]],
    judging_window_minutes: int,
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    duration_raw = winning_facts.get("event.duration_minutes")
    if duration_raw is None or int(duration_raw) <= 0:
        return {
            "status": "missing",
            "missing_keys": ["event.duration_minutes"],
            "duration_minutes": 0,
            "break_minutes": 0,
            "blocks": [],
            "warnings": ["Missing event.duration_minutes"],
        }

    duration = int(duration_raw)
    opening_mins = int(policy.get("opening_minutes", 15))
    closing_mins = int(policy.get("closing_minutes", 15))
    split = float(policy.get("build_split_before_breaks", 0.5))

    # Extract schedule_block constraints in order
    break_blocks: List[Dict[str, Any]] = []
    seen_targets = set()
    for c in constraints:
        if c.get("area") == "schedule" and c.get("type") == "schedule_block":
            target = str(c.get("target") or "break").strip().lower()
            try:
                b_mins = int(c.get("value") or 0)
            except Exception:
                b_mins = 0
            if b_mins <= 0:
                continue
            # If a newer constraint updates the same block name, update in place
            if target in seen_targets:
                for bb in break_blocks:
                    if bb["slug"] == target:
                        bb["minutes"] = b_mins
            else:
                seen_targets.add(target)
                break_blocks.append(
                    {
                        "slug": target,
                        "name": _humanize_block(target),
                        "minutes": b_mins,
                    }
                )

    breaks_total = sum(b["minutes"] for b in break_blocks)
    build_total = duration - opening_mins - breaks_total - judging_window_minutes - closing_mins

    status = "ok"
    shortfall = 0
    warnings: List[str] = []
    if build_total < 0:
        status = "overflow"
        shortfall = -build_total
        warnings.append(f"Schedule blocks exceed duration by {shortfall} minutes")
        build1 = 0
        build2 = 0
    else:
        build1 = math.floor(build_total * split)
        build2 = build_total - build1

    # Handle start_time and schedule_window constraints
    start_clock_str = winning_facts.get("event.start_time")
    start_clock_mins = _parse_hhmm(str(start_clock_str)) if start_clock_str else None

    window_start_mins: Optional[int] = None
    window_end_mins: Optional[int] = None
    for c in constraints:
        if c.get("area") == "schedule" and c.get("type") == "schedule_window":
            t = str(c.get("target") or "").strip().lower()
            v_mins = _parse_hhmm(str(c.get("value") or ""))
            if v_mins is not None:
                if "start" in t:
                    window_start_mins = v_mins
                elif "end" in t:
                    window_end_mins = v_mins

    if start_clock_mins is None and window_start_mins is not None:
        start_clock_mins = window_start_mins
    elif start_clock_mins is None and window_end_mins is not None:
        start_clock_mins = window_end_mins - duration

    if (
        window_start_mins is not None
        and window_end_mins is not None
        and (window_end_mins - window_start_mins) < duration
    ):
        status = "overflow"
        warnings.append("Schedule window smaller than event duration")

    raw_sequence: List[Dict[str, Any]] = [{"name": "Opening", "minutes": opening_mins}]
    if break_blocks:
        raw_sequence.append({"name": "Build 1", "minutes": build1})
        for bb in break_blocks:
            raw_sequence.append({"name": bb["name"], "slug": bb["slug"], "minutes": bb["minutes"]})
        raw_sequence.append({"name": "Build 2", "minutes": build2})
    else:
        raw_sequence.append({"name": "Build", "minutes": build1 + build2})

    raw_sequence.append({"name": "Judging", "minutes": judging_window_minutes})
    raw_sequence.append({"name": "Closing", "minutes": closing_mins})

    blocks: List[Dict[str, Any]] = []
    offset = 0
    for item in raw_sequence:
        m = int(item["minutes"])
        start_off = offset
        end_off = offset + m
        offset = end_off
        clk_start = _format_hhmm(start_clock_mins + start_off) if start_clock_mins is not None else None
        clk_end = _format_hhmm(start_clock_mins + end_off) if start_clock_mins is not None else None
        blocks.append(
            {
                "name": item["name"],
                "slug": item.get("slug", item["name"].lower().replace(" ", "_")),
                "start": start_off,
                "end": end_off,
                "start_offset": start_off,
                "end_offset": end_off,
                "minutes": m,
                "clock_start": clk_start,
                "clock_end": clk_end,
            }
        )

    return {
        "status": status,
        "shortfall": shortfall,
        "duration_minutes": duration,
        "total_minutes": offset,
        "break_minutes": breaks_total,
        "judging_window_minutes": judging_window_minutes,
        "start_clock": _format_hhmm(start_clock_mins) if start_clock_mins is not None else None,
        "end_clock": _format_hhmm(start_clock_mins + offset) if start_clock_mins is not None else None,
        "blocks": blocks,
        "warnings": warnings,
    }
