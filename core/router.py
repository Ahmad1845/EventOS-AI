"""Router module: maps changed fact keys and constraint areas to affected solvers per Section 14."""

from typing import Iterable, List, Set


PLANNING_ORDER: List[str] = ["judging", "venue", "food", "schedule", "budget"]


def affected_areas(changed_keys: Iterable[str], is_fresh: bool = False) -> List[str]:
    """
    Map changed keys to the ordered list of areas to re-solve per Section 14 table.
    Always returns areas in planning order: judging, venue, food, schedule, budget.
    """
    if is_fresh:
        return list(PLANNING_ORDER)

    areas: Set[str] = set()

    for key in changed_keys:
        k = key.strip().lower()
        if k in ("event.students", "event.team_size", "event.teams"):
            areas.update(["venue", "food", "judging", "schedule", "budget"])
        elif k == "event.staff":
            areas.update(["venue", "food", "budget"])
        elif k in ("event.duration_minutes", "event.start_time"):
            areas.add("schedule")
        elif k == "budget.cap":
            areas.add("budget")
        elif (
            k.startswith("budget.committed.")
            or k.startswith("budget.approved_extra.")
            or k.startswith("budget.request.")
        ):
            areas.add("budget")
        elif k.startswith("venue.option.") or k == "venue.choice":
            areas.update(["venue", "budget"])
        elif k.startswith("food.option.") or k in ("food.delivery_fee", "food.service_charge_percent", "food.quantity"):
            areas.update(["food", "budget"])
        elif k in ("judging.confirmed", "judging.engaged"):
            areas.update(["judging", "venue", "food", "schedule", "budget"])
        elif k == "judging.rate":
            areas.update(["judging", "budget"])
        elif k in ("judging.minutes_per_team", "judging.max_teams_per_judge"):
            areas.update(["judging", "schedule", "venue", "food", "budget"])
        elif k.startswith("custom.") or k.startswith("constraint."):
            parts = k.split(".")
            if len(parts) >= 2 and parts[1] in PLANNING_ORDER:
                areas.add(parts[1])
                areas.add("budget")
            else:
                areas.update(PLANNING_ORDER)
        else:
            # Fallback if an unknown key prefix is encountered
            areas.update(PLANNING_ORDER)

    return [a for a in PLANNING_ORDER if a in areas]


def model_call_areas() -> List[str]:
    """Per Section 14: list of tags that will call a model, always ['reading'] in this design."""
    return ["reading"]
