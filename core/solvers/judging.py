"""Judging solver per Section 15.2."""

import math
from typing import Any, Dict, List, Optional


def solve_judging(
    teams: Optional[int],
    winning_facts: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    missing: List[str] = []
    if teams is None or teams <= 0:
        missing.append("event.teams")
    max_teams = winning_facts.get("judging.max_teams_per_judge")
    if max_teams is None or float(max_teams) <= 0:
        missing.append("judging.max_teams_per_judge")
    mins_per_team = winning_facts.get("judging.minutes_per_team")
    if mins_per_team is None or float(mins_per_team) <= 0:
        missing.append("judging.minutes_per_team")
    confirmed = winning_facts.get("judging.confirmed")
    if confirmed is None:
        missing.append("judging.confirmed")
    rate = winning_facts.get("judging.rate")
    if rate is None:
        missing.append("judging.rate")

    if missing:
        return {
            "status": "missing",
            "missing_keys": missing,
            "teams": teams or 0,
            "required": 0,
            "confirmed": int(confirmed) if confirmed is not None else 0,
            "engaged": 0,
            "max_teams_per_judge": int(max_teams) if max_teams is not None else 0,
            "minutes_per_team": int(mins_per_team) if mins_per_team is not None else 0,
            "rate": int(rate) if rate is not None else 0,
            "assignments": [],
            "window_minutes": 0,
            "honorarium_total": 0,
            "warnings": [f"Missing judging keys: {', '.join(missing)}"],
        }

    t_count = int(teams)
    m_limit = int(max_teams)
    t_mins = int(mins_per_team)
    c_count = int(confirmed)
    r_val = int(rate)

    required = math.ceil(t_count / m_limit)
    mode = str(policy.get("judges_engaged", "minimum_required")).lower()
    if mode == "all_confirmed":
        engaged = c_count
    else:
        engaged = required

    override_engaged = winning_facts.get("judging.engaged")
    if override_engaged is not None:
        engaged = int(override_engaged)

    status = "ok"
    shortfall = 0
    warnings: List[str] = []
    if c_count < required:
        status = "insufficient"
        shortfall = required - c_count
        warnings.append(f"Confirmed judges ({c_count}) below required ({required})")

    # Round-robin assignment: team i (0..teams-1) goes to judge (i mod engaged)
    assignments: List[Dict[str, Any]] = []
    if engaged > 0:
        buckets: List[List[int]] = [[] for _ in range(engaged)]
        for i in range(t_count):
            buckets[i % engaged].append(i + 1)
        for j_idx, t_list in enumerate(buckets):
            assignments.append({"judge": j_idx + 1, "teams": t_list})
        k_actual = math.ceil(t_count / engaged)
    else:
        k_actual = 0

    window_minutes = k_actual * t_mins
    honorarium_total = engaged * r_val

    return {
        "status": status,
        "shortfall": shortfall,
        "teams": t_count,
        "required": required,
        "confirmed": c_count,
        "engaged": engaged,
        "max_teams_per_judge": m_limit,
        "max_teams_actual": k_actual,
        "minutes_per_team": t_mins,
        "rate": r_val,
        "assignments": assignments,
        "window_minutes": window_minutes,
        "honorarium_total": honorarium_total,
        "warnings": warnings,
    }
