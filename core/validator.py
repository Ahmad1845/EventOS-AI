"""Validator module: independently recomputes and checks the 6 official checks + constraints + floors per Section 17."""

import math
from typing import Any, Dict, List

from core.constraints import evaluate_constraints
from core.factstore import get_winning_facts


def validate_plan(
    plan: Dict[str, Any],
    facts: List[Dict[str, Any]],
    constraints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Run all 8 checks independently from raw facts per Section 17.
    Returns {passed: bool, checks: [...], failures: [...], unevaluated_warnings: [...]}.
    """
    winning = get_winning_facts(facts)

    hc = plan.get("headcount") or {}
    venue = plan.get("venue") or {}
    food = plan.get("food") or {}
    judging = plan.get("judging") or {}
    sched = plan.get("schedule") or {}
    budget = plan.get("budget") or {}

    failures: List[Dict[str, str]] = []
    checks: List[Dict[str, Any]] = []

    # Raw independent values
    raw_students = int(winning.get("event.students", 0))
    raw_staff = int(winning.get("event.staff", 0))
    raw_team_size = int(winning.get("event.team_size", 0))
    raw_teams = (
        int(winning.get("event.teams"))
        if winning.get("event.teams") is not None
        else (math.ceil(raw_students / raw_team_size) if raw_team_size > 0 else 0)
    )
    raw_duration = int(winning.get("event.duration_minutes", 0))
    raw_cap = int(winning.get("budget.cap", 0))
    raw_rate = int(winning.get("judging.rate", 0))
    raw_confirmed = int(winning.get("judging.confirmed", 0))
    raw_max_teams = int(winning.get("judging.max_teams_per_judge", 0))
    raw_mins_per_team = int(winning.get("judging.minutes_per_team", 0))
    raw_required_judges = math.ceil(raw_teams / raw_max_teams) if raw_max_teams > 0 else 0

    engaged = int(judging.get("engaged", 0))
    expected_headcount = raw_students + raw_staff + engaged

    # Check 8: floors (evaluated first so override floor failures use exact templates)
    floors_ok = True
    floors_reasons: List[str] = []

    food_qty = int(food.get("quantity", 0))
    if food_qty < expected_headcount:
        floors_ok = False
        msg = f"Rejected: food quantity {food_qty} is below the {expected_headcount} people to feed"
        floors_reasons.append(msg)
        failures.append({"check": "food_quantity", "reason": msg})

    if engaged < raw_required_judges:
        floors_ok = False
        msg = f"Rejected: {engaged} judges engaged, {raw_required_judges} needed at {raw_max_teams} teams each"
        floors_reasons.append(msg)
        failures.append({"check": "judges", "reason": msg})

    v_cap = int(venue.get("capacity", 0))
    v_name = venue.get("name") or venue.get("slug") or "Venue"
    if v_cap < expected_headcount:
        floors_ok = False
        msg = f"Rejected: {v_name} seats {v_cap}, below headcount {expected_headcount}"
        floors_reasons.append(msg)
        failures.append({"check": "venue_fit", "reason": msg})

    # Check 1: figures (independent arithmetic check)
    plan_hc = int(hc.get("total", -1))
    plan_teams = int(judging.get("teams", -1))
    f_unit = int(food.get("unit_price", 0))
    f_deliv = int(food.get("delivery_fee", 0))
    f_cost = int(food.get("cost", -1))
    expected_f_cost = food_qty * f_unit + f_deliv

    j_hon = int(judging.get("honorarium_total", -1))
    expected_j_hon = engaged * raw_rate

    b_items = budget.get("items") or []
    b_sum = sum(int(i.get("amount", 0)) for i in b_items)
    b_total = int(budget.get("total", -1))

    figures_ok = (
        plan_hc == expected_headcount
        and plan_teams == raw_teams
        and f_cost == expected_f_cost
        and j_hon == expected_j_hon
        and b_total == b_sum
        and raw_students > 0
        and raw_teams > 0
    )
    if not figures_ok:
        failures.append(
            {
                "check": "figures",
                "reason": "Rejected: plan arithmetic figures do not match independent recomputation",
            }
        )
    checks.append(
        {
            "id": "figures",
            "passed": figures_ok,
            "detail": (
                f"headcount={plan_hc} ({raw_students}+{raw_staff}+{engaged}), "
                f"teams={plan_teams}, food={f_cost}, honorarium={j_hon}, total={b_total}"
            ),
        }
    )

    # Check 2: budget
    budget_ok = raw_cap > 0 and b_total <= raw_cap
    if not budget_ok:
        overage = max(0, b_total - raw_cap)
        msg = f"Rejected: total Rs {b_total:,} exceeds the approved cap of Rs {raw_cap:,} by Rs {overage:,}".replace(
            ",", ""
        )
        failures.append({"check": "budget", "reason": msg})
    checks.append(
        {
            "id": "budget",
            "passed": budget_ok,
            "detail": f"Rs {b_total} / Rs {raw_cap} (remaining Rs {raw_cap - b_total})",
        }
    )

    # Check 3: venue_fit
    req_features = [
        str(c.get("target") or "").strip().lower()
        for c in constraints
        if c.get("area") == "venue" and c.get("type") == "require_feature" and c.get("hard", True)
    ]
    v_feats = [str(f).lower() for f in (venue.get("features") or [])]
    feats_ok = all(
        any(rf == vf or rf in vf or vf in rf for vf in v_feats) for rf in req_features
    )
    venue_ok = (
        venue.get("status") == "ok"
        and v_cap >= expected_headcount
        and feats_ok
    )
    if not venue_ok and v_cap >= expected_headcount:
        if not feats_ok:
            failures.append(
                {
                    "check": "venue_fit",
                    "reason": f"Rejected: {v_name} does not have required features ({', '.join(req_features)})",
                }
            )
        else:
            failures.append(
                {
                    "check": "venue_fit",
                    "reason": f"Rejected: no venue fits headcount {expected_headcount} and feature requirements",
                }
            )
    checks.append(
        {
            "id": "venue_fit",
            "passed": venue_ok,
            "detail": f"{v_name} capacity {v_cap} >= {expected_headcount}",
        }
    )

    # Check 4: schedule
    blocks = sched.get("blocks") or []
    sum_blocks = sum(int(b.get("minutes", 0)) for b in blocks)
    expected_j_win = (
        math.ceil(raw_teams / engaged) * raw_mins_per_team if engaged > 0 else 0
    )
    j_blocks = [b for b in blocks if b.get("name") == "Judging"]
    j_block_ok = bool(j_blocks) and int(j_blocks[0].get("minutes", -1)) == expected_j_win

    no_neg_or_overlap = True
    prev_end = 0
    for b in blocks:
        if int(b.get("minutes", 0)) < 0 or int(b.get("start", 0)) != prev_end:
            no_neg_or_overlap = False
            break
        prev_end = int(b.get("end", 0))

    req_sched_blocks = [
        c
        for c in constraints
        if c.get("area") == "schedule" and c.get("type") == "schedule_block" and c.get("hard", True)
    ]
    req_blocks_ok = True
    for rsb in req_sched_blocks:
        t_slug = str(rsb.get("target") or "").lower().replace(" ", "_")
        r_min = int(rsb.get("value") or 0)
        if not any(
            (t_slug in str(b.get("slug", "")).lower() or str(b.get("slug", "")).lower() in t_slug)
            and int(b.get("minutes", 0)) >= r_min
            for b in blocks
        ):
            req_blocks_ok = False
            break

    schedule_ok = (
        sched.get("status") == "ok"
        and raw_duration > 0
        and sum_blocks == raw_duration
        and j_block_ok
        and no_neg_or_overlap
        and req_blocks_ok
    )
    if not schedule_ok:
        failures.append(
            {
                "check": "schedule",
                "reason": f"Rejected: schedule invalid (sum {sum_blocks} vs duration {raw_duration})",
            }
        )
    checks.append(
        {
            "id": "schedule",
            "passed": schedule_ok,
            "detail": f"{len(blocks)} blocks summing to {sum_blocks}/{raw_duration} min",
        }
    )

    # Check 5: judges
    assignments = judging.get("assignments") or []
    max_assigned = max((len(a.get("teams", [])) for a in assignments), default=0)
    judges_ok = (
        judging.get("status") == "ok"
        and engaged >= raw_required_judges
        and engaged <= raw_confirmed
        and max_assigned <= raw_max_teams
        and raw_required_judges > 0
    )
    if not judges_ok and engaged >= raw_required_judges:
        failures.append(
            {
                "check": "judges",
                "reason": f"Rejected: {engaged} judges engaged vs {raw_confirmed} confirmed ({raw_required_judges} needed)",
            }
        )
    checks.append(
        {
            "id": "judges",
            "passed": judges_ok,
            "detail": f"{engaged} engaged (required {raw_required_judges}, confirmed {raw_confirmed}, max {max_assigned} teams/judge)",
        }
    )

    # Check 6: coverage
    bad_statuses = {"missing", "insufficient", "no_fit", "overflow", "over_budget"}
    area_statuses = [
        venue.get("status"),
        sched.get("status"),
        food.get("status"),
        judging.get("status"),
        budget.get("status"),
    ]
    coverage_ok = all(s not in bad_statuses and s is not None for s in area_statuses)
    if not coverage_ok:
        failures.append(
            {
                "check": "coverage",
                "reason": "Rejected: one or more planning areas incomplete or out of bounds",
            }
        )
    checks.append(
        {
            "id": "coverage",
            "passed": coverage_ok,
            "detail": "all 5 areas (venue, schedule, food, judging, budget) solved and covered",
        }
    )

    # Check 7: constraints
    c_failures, unevaluated_warnings = evaluate_constraints(plan, constraints)
    constraints_ok = len(c_failures) == 0
    for cf in c_failures:
        failures.append(cf)
    checks.append(
        {
            "id": "constraints",
            "passed": constraints_ok,
            "detail": "all typed constraints satisfied"
            if constraints_ok
            else c_failures[0]["reason"],
        }
    )

    # Append Check 8 summary to checks list
    checks.append(
        {
            "id": "floors",
            "passed": floors_ok,
            "detail": "all quantity and capacity floors satisfied"
            if floors_ok
            else floors_reasons[0],
        }
    )

    passed = (
        figures_ok
        and budget_ok
        and venue_ok
        and schedule_ok
        and judges_ok
        and coverage_ok
        and constraints_ok
        and floors_ok
    )

    return {
        "passed": passed,
        "checks": checks,
        "failures": failures,
        "unevaluated_warnings": unevaluated_warnings,
    }
