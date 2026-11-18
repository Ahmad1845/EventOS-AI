"""Generic constraint model and evaluator per Section 16."""

from typing import Any, Dict, List, Tuple

from core.solvers.venue import feature_matches


def extract_plan_metrics(plan: Dict[str, Any]) -> Dict[str, float]:
    """Expose flat dictionary of plan metrics per Section 16.2."""
    hc = plan.get("headcount") or {}
    venue = plan.get("venue") or {}
    food = plan.get("food") or {}
    judging = plan.get("judging") or {}
    sched = plan.get("schedule") or {}
    budget = plan.get("budget") or {}

    blocks = sched.get("blocks") or []
    total_sched_mins = sum(int(b.get("minutes", 0)) for b in blocks)
    break_mins = int(sched.get("break_minutes", 0))
    if break_mins == 0 and blocks:
        break_mins = sum(
            int(b.get("minutes", 0))
            for b in blocks
            if b.get("name") not in ("Opening", "Build", "Build 1", "Build 2", "Judging", "Closing")
        )

    return {
        "event.headcount": float(hc.get("total", 0)),
        "event.students": float(hc.get("students", 0)),
        "event.staff": float(hc.get("staff", 0)),
        "event.teams": float(judging.get("teams", 0)),
        "venue.capacity": float(venue.get("capacity", 0)),
        "venue.price": float(venue.get("price", 0)),
        "venue.slack": float(venue.get("slack", 0)),
        "food.quantity": float(food.get("quantity", 0)),
        "food.unit_price": float(food.get("unit_price", 0)),
        "food.cost": float(food.get("cost", 0)),
        "judging.engaged": float(judging.get("engaged", 0)),
        "judging.required": float(judging.get("required", 0)),
        "judging.window_minutes": float(judging.get("window_minutes", 0)),
        "judging.honorarium_total": float(judging.get("honorarium_total", 0)),
        "schedule.total_minutes": float(total_sched_mins),
        "schedule.break_minutes": float(break_mins),
        "budget.total": float(budget.get("total", 0)),
        "budget.cap": float(budget.get("cap", 0)),
        "budget.remaining": float(budget.get("remaining", 0)),
    }


def _compare_op(actual: float, op: str, expected: float) -> bool:
    op = op.strip()
    if op in ("<=", "=<"):
        return actual <= expected
    if op in (">=", "=>"):
        return actual >= expected
    if op in ("==", "="):
        return actual == expected
    if op == "<":
        return actual < expected
    if op == ">":
        return actual > expected
    if op in ("!=", "<>"):
        return actual != expected
    return False


def evaluate_constraints(
    plan: Dict[str, Any], constraints: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Evaluate all constraints on candidate plan per Section 16.
    Returns (failures, unevaluated_warnings).
    """
    metrics = extract_plan_metrics(plan)
    failures: List[Dict[str, Any]] = []
    unevaluated: List[str] = []

    venue = plan.get("venue") or {}
    food = plan.get("food") or {}
    sched = plan.get("schedule") or {}

    for c in constraints:
        ctype = str(c.get("type") or "other").strip().lower()
        target = str(c.get("target") or "").strip().lower()
        hard = bool(c.get("hard", True))
        text = str(c.get("text") or f"{ctype} {target}").strip()

        if ctype == "other" or not hard:
            unevaluated.append(f"unevaluated constraint ({c.get('area', 'general')}): {text}")
            continue

        if ctype == "metric_limit":
            if target not in metrics:
                unevaluated.append(f"unevaluated metric_limit ({target}): {text}")
                continue
            try:
                limit_val = float(c.get("value"))
            except Exception:
                unevaluated.append(f"unevaluated metric_limit value ({target}): {text}")
                continue
            op = str(c.get("op") or "<=")
            actual_val = metrics[target]
            if not _compare_op(actual_val, op, limit_val):
                act_int = int(actual_val) if actual_val.is_integer() else actual_val
                lim_int = int(limit_val) if limit_val.is_integer() else limit_val
                failures.append(
                    {
                        "check": "constraints",
                        "reason": f"Rejected: constraint {target} {op} {lim_int} failed (actual {act_int})",
                    }
                )

        elif ctype == "require_feature":
            v_feats = [str(f).lower() for f in (venue.get("features") or [])]
            matched = feature_matches(target, v_feats)
            if not matched:
                v_name = venue.get("name") or venue.get("slug") or "chosen venue"
                failures.append(
                    {
                        "check": "venue_fit",
                        "reason": f"Rejected: {v_name} missing required feature {target}",
                    }
                )

        elif ctype == "forbid_item":
            c_area = str(c.get("area") or "food").strip().lower()
            if c_area == "venue":
                chosen_venue = str(venue.get("slug") or venue.get("name") or "").lower().replace(" ", "_")
                if target and (target == chosen_venue or target in chosen_venue or chosen_venue in target):
                    failures.append(
                        {
                            "check": "constraints",
                            "reason": f"Rejected: forbidden/unavailable venue {chosen_venue} selected",
                        }
                    )
            else:
                chosen_food = str(food.get("slug") or food.get("option") or "").lower()
                if target and (target == chosen_food or target in chosen_food.split("_") or target in chosen_food):
                    failures.append(
                        {
                            "check": "constraints",
                            "reason": f"Rejected: food option {chosen_food} contains forbidden item {target}",
                        }
                    )

        elif ctype == "schedule_block":
            try:
                req_mins = int(c.get("value") or 0)
            except Exception:
                req_mins = 0
            blocks = sched.get("blocks") or []
            found = False
            for b in blocks:
                b_slug = str(b.get("slug") or b.get("name", "")).lower().replace(" ", "_")
                if target in b_slug or b_slug in target:
                    if int(b.get("minutes", 0)) >= req_mins:
                        found = True
                        break
            if not found:
                failures.append(
                    {
                        "check": "schedule",
                        "reason": f"Rejected: required schedule block {target} ({req_mins} min) missing or short",
                    }
                )

        elif ctype == "schedule_window":
            val_clock = str(c.get("value") or "").strip()
            if "start" in target and sched.get("start_clock"):
                if sched["start_clock"] != val_clock:
                    failures.append(
                        {
                            "check": "schedule",
                            "reason": f"Rejected: schedule start {sched['start_clock']} violates window {val_clock}",
                        }
                    )
            elif "end" in target and sched.get("end_clock"):
                # End clock must be <= window end
                if sched["end_clock"] > val_clock:
                    failures.append(
                        {
                            "check": "schedule",
                            "reason": f"Rejected: schedule end {sched['end_clock']} exceeds window {val_clock}",
                        }
                    )

    return failures, unevaluated
