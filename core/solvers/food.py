"""Food solver per Section 15.4."""

from typing import Any, Dict, List


def _humanize_slug(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("_") if w)


def extract_food_options(winning_facts: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    options: Dict[str, Dict[str, Any]] = {}
    for key, val in winning_facts.items():
        if not key.startswith("food.option."):
            continue
        parts = key.split(".")
        if len(parts) < 4:
            continue
        slug = parts[2]
        field = parts[3]
        opt = options.setdefault(
            slug,
            {
                "slug": slug,
                "name": _humanize_slug(slug),
                "unit_price": None,
                "is_default": any(w in slug for w in ("standard", "regular", "default")),
            },
        )
        if field == "unit_price":
            try:
                opt["unit_price"] = int(val)
            except Exception:
                pass
        elif field == "is_default":
            opt["is_default"] = bool(val)
    return {k: v for k, v in options.items() if v["unit_price"] is not None}


def solve_food(
    headcount: int,
    winning_facts: Dict[str, Any],
    constraints: List[Dict[str, Any]],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    options_map = extract_food_options(winning_facts)
    if not options_map:
        return {
            "status": "missing",
            "missing_keys": ["food.option.*.unit_price"],
            "option": None,
            "slug": None,
            "unit_price": 0,
            "quantity": headcount,
            "delivery_fee": 0,
            "cost": 0,
            "fallback_options": [],
            "warnings": ["No food options found"],
        }

    forbid_targets: List[str] = []
    for c in constraints:
        if c.get("area") == "food" and c.get("type") == "forbid_item" and c.get("hard", True):
            t = str(c.get("target") or "").strip().lower()
            if t:
                forbid_targets.append(t)

    allowed: List[Dict[str, Any]] = []
    for slug, opt in options_map.items():
        words = set(slug.split("_"))
        if any(ft == slug or ft in words or ft in slug for ft in forbid_targets):
            continue
        allowed.append(opt)

    if not allowed:
        return {
            "status": "no_fit",
            "option": None,
            "slug": None,
            "unit_price": 0,
            "quantity": headcount,
            "delivery_fee": 0,
            "cost": 0,
            "fallback_options": [],
            "warnings": ["All food options excluded by forbid_item constraints"],
        }

    # Option order per Section 15.4: default option first, then others by descending price
    allowed.sort(key=lambda x: (0 if x["is_default"] else 1, -x["unit_price"], x["slug"]))
    chosen = allowed[0]

    # Fallback chain used by budget solver goes by ascending price
    fallback_chain = sorted(allowed, key=lambda x: (x["unit_price"], x["slug"]))

    override_qty = winning_facts.get("food.quantity")
    quantity = int(override_qty) if override_qty is not None else headcount

    raw_deliv = winning_facts.get("food.delivery_fee", 0)
    delivery_fee = int(raw_deliv) if isinstance(raw_deliv, (int, float)) else 0

    cost = quantity * chosen["unit_price"] + delivery_fee

    return {
        "status": "ok",
        "option": chosen["slug"],
        "name": chosen["name"],
        "slug": chosen["slug"],
        "unit_price": chosen["unit_price"],
        "quantity": quantity,
        "delivery_fee": delivery_fee,
        "cost": cost,
        "fallback_options": fallback_chain,
        "override_used": override_qty is not None,
        "warnings": [],
    }
