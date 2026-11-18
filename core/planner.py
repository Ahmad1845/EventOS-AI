"""Planner module: orchestrates domain solvers in dependency order per Section 15."""

import copy
import math
from typing import Any, Dict, List, Optional

from core.factstore import get_winning_facts
from core.solvers.budget import solve_budget
from core.solvers.food import solve_food
from core.solvers.judging import solve_judging
from core.solvers.schedule import solve_schedule
from core.solvers.venue import solve_venue
from core.trace import Trace


ACRONYMS = {"dj", "av", "ac", "pa", "mc", "it", "vip", "wifi", "tv", "led", "id"}


def _humanize_slug(slug: str) -> str:
    parts = [w for w in slug.split("_") if w]
    out: List[str] = []
    for w in parts:
        lw = w.lower()
        if lw in ACRONYMS or (len(w) == 1 and w.isalpha()):
            out.append(lw.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def build_plan(
    facts: List[Dict[str, Any]],
    constraints: List[Dict[str, Any]],
    previous_plan: Optional[Dict[str, Any]],
    areas: List[str],
    policy: Dict[str, Any],
    trace: Optional[Trace] = None,
) -> Dict[str, Any]:
    """
    Build a candidate plan per Section 15.
    Areas not in `areas` are copied from `previous_plan`.
    Solvers run in order: judging, venue, food, schedule, budget.
    """
    winning = get_winning_facts(facts)
    area_set = set(areas) if previous_plan is not None else {
        "judging",
        "venue",
        "food",
        "schedule",
        "budget",
    }

    warnings: List[str] = []

    students_raw = winning.get("event.students")
    students = int(students_raw) if students_raw is not None else 0
    if students_raw is None:
        warnings.append("Missing event.students")

    team_size_raw = winning.get("event.team_size")
    teams_raw = winning.get("event.teams")
    if teams_raw is not None:
        teams: Optional[int] = int(teams_raw)
    elif students_raw is not None and team_size_raw is not None and int(team_size_raw) > 0:
        teams = math.ceil(int(students_raw) / int(team_size_raw))
    else:
        teams = None

    staff_raw = winning.get("event.staff")
    if staff_raw is None:
        staff = 0
        warnings.append("event.staff absent; defaulted to 0")
    else:
        staff = int(staff_raw)

    # 1. Judging
    if "judging" in area_set or previous_plan is None:
        judging_res = solve_judging(teams, winning, policy)
        warnings.extend(judging_res.get("warnings", []))
        if trace:
            trace.python_event(
                "SOLVE",
                f"judging -> {judging_res.get('engaged')} engaged of {judging_res.get('confirmed')} confirmed "
                f"(required {judging_res.get('required')}, window {judging_res.get('window_minutes')} min, "
                f"honorarium Rs {judging_res.get('honorarium_total')})",
            )
    else:
        judging_res = copy.deepcopy(previous_plan["judging"])

    judges_engaged = int(judging_res.get("engaged", 0))
    headcount = students + staff + judges_engaged

    # 2. Venue
    if "venue" in area_set or previous_plan is None:
        venue_res = solve_venue(headcount, winning, constraints)
        warnings.extend(venue_res.get("warnings", []))
        if trace:
            trace.python_event(
                "SOLVE",
                f"venue -> {venue_res.get('name')} (capacity {venue_res.get('capacity')} >= {headcount}, "
                f"Rs {venue_res.get('price')})",
            )
    else:
        venue_res = copy.deepcopy(previous_plan["venue"])

    # 3. Food
    if "food" in area_set or previous_plan is None:
        food_res = solve_food(headcount, winning, constraints, policy)
        warnings.extend(food_res.get("warnings", []))
        if trace:
            trace.python_event(
                "SOLVE",
                f"food -> {food_res.get('option')} ({food_res.get('quantity')} x Rs {food_res.get('unit_price')} "
                f"+ delivery Rs {food_res.get('delivery_fee')} = Rs {food_res.get('cost')})",
            )
    else:
        food_res = copy.deepcopy(previous_plan["food"])

    # 4. Schedule
    if "schedule" in area_set or previous_plan is None:
        schedule_res = solve_schedule(
            winning,
            constraints,
            int(judging_res.get("window_minutes", 0)),
            policy,
        )
        warnings.extend(schedule_res.get("warnings", []))
        if trace:
            trace.python_event(
                "SOLVE",
                f"schedule -> {len(schedule_res.get('blocks', []))} blocks totaling "
                f"{schedule_res.get('total_minutes')}/{schedule_res.get('duration_minutes')} min",
            )
    else:
        schedule_res = copy.deepcopy(previous_plan["schedule"])

    # 5. Budget
    if "budget" in area_set or previous_plan is None:
        budget_res = solve_budget(
            venue_res=venue_res,
            food_res=food_res,
            judging_res=judging_res,
            active_facts=facts,
            winning_facts=winning,
            allow_venue_downgrade=("venue" in area_set or previous_plan is None),
            allow_food_downgrade=("food" in area_set or previous_plan is None),
            trace=trace,
        )
        warnings.extend(budget_res.get("warnings", []))
        if trace:
            trace.python_event(
                "SOLVE",
                f"budget -> total Rs {budget_res.get('total')} / cap Rs {budget_res.get('cap')} "
                f"(remaining Rs {budget_res.get('remaining')})",
            )
    else:
        budget_res = copy.deepcopy(previous_plan["budget"])

    # Collect excluded unapproved requests per Section 13.5
    excluded_requests: List[Dict[str, Any]] = []
    if bool(policy.get("exclude_unapproved_requests", True)):
        for key in sorted(winning.keys()):
            if key.startswith("budget.request."):
                slug = key.split(".", 2)[2]
                amt = winning[key]
                excluded_requests.append(
                    {
                        "item": _humanize_slug(slug),
                        "slug": slug,
                        "amount": int(amt) if isinstance(amt, (int, float)) else amt,
                        "reason": "no approval stated",
                    }
                )

    prev_ver = int(previous_plan.get("version", 0)) if previous_plan else 0
    candidate_plan: Dict[str, Any] = {
        "valid": True,
        "version": prev_ver + 1,
        "headcount": {
            "students": students,
            "staff": staff,
            "judges": judges_engaged,
            "total": headcount,
        },
        "venue": {
            "status": venue_res.get("status", "ok"),
            "slug": venue_res.get("slug"),
            "name": venue_res.get("name"),
            "capacity": int(venue_res.get("capacity", 0)),
            "price": int(venue_res.get("price", 0)),
            "slack": int(venue_res.get("slack", 0)),
            "features": venue_res.get("features", []),
            "rejected_options": venue_res.get("rejected_options", []),
            "skipped_fitting": venue_res.get("skipped_fitting", []),
        },
        "schedule": {
            "status": schedule_res.get("status", "ok"),
            "duration_minutes": int(schedule_res.get("duration_minutes", 0)),
            "total_minutes": int(schedule_res.get("total_minutes", 0)),
            "break_minutes": int(schedule_res.get("break_minutes", 0)),
            "start_clock": schedule_res.get("start_clock"),
            "end_clock": schedule_res.get("end_clock"),
            "blocks": schedule_res.get("blocks", []),
        },
        "food": {
            "status": food_res.get("status", "ok"),
            "option": food_res.get("option"),
            "name": food_res.get("name"),
            "slug": food_res.get("slug"),
            "unit_price": int(food_res.get("unit_price", 0)),
            "quantity": int(food_res.get("quantity", 0)),
            "delivery_fee": int(food_res.get("delivery_fee", 0)),
            "service_charge_percent": food_res.get("service_charge_percent", 0),
            "service_charge_amount": int(food_res.get("service_charge_amount", 0)),
            "cost": int(food_res.get("cost", 0)),
        },
        "judging": {
            "status": judging_res.get("status", "ok"),
            "teams": int(judging_res.get("teams", 0)),
            "required": int(judging_res.get("required", 0)),
            "confirmed": int(judging_res.get("confirmed", 0)),
            "engaged": judges_engaged,
            "max_teams_per_judge": int(judging_res.get("max_teams_per_judge", 0)),
            "minutes_per_team": int(judging_res.get("minutes_per_team", 0)),
            "rate": int(judging_res.get("rate", 0)),
            "assignments": judging_res.get("assignments", []),
            "window_minutes": int(judging_res.get("window_minutes", 0)),
            "honorarium_total": int(judging_res.get("honorarium_total", 0)),
        },
        "budget": {
            "status": budget_res.get("status", "ok"),
            "cap": int(budget_res.get("cap", 0)),
            "total": int(budget_res.get("total", 0)),
            "remaining": int(budget_res.get("remaining", 0)),
            "items": budget_res.get("items", []),
        },
        "excluded_requests": excluded_requests,
        "warnings": warnings,
        "recomputed_areas": list(areas),
    }
    return candidate_plan
