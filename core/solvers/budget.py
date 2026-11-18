"""Budget solver with deterministic downgrade chain per Section 15.6."""

from typing import Any, Dict, List, Optional

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


def solve_budget(
    venue_res: Dict[str, Any],
    food_res: Dict[str, Any],
    judging_res: Dict[str, Any],
    active_facts: List[Dict[str, Any]],
    winning_facts: Dict[str, Any],
    allow_venue_downgrade: bool,
    allow_food_downgrade: bool,
    trace: Optional[Trace] = None,
) -> Dict[str, Any]:
    cap_raw = winning_facts.get("budget.cap")
    if cap_raw is None:
        return {
            "status": "missing",
            "missing_keys": ["budget.cap"],
            "cap": 0,
            "total": 0,
            "remaining": 0,
            "items": [],
            "warnings": ["Missing budget.cap"],
        }

    cap = int(cap_raw)

    # Gather committed and approved_extra facts with source message numbers
    fact_msg_map: Dict[str, int] = {}
    for f in active_facts:
        if f.get("superseded_by") is None and f.get("key"):
            fact_msg_map[f["key"]] = int(f.get("seq") or f.get("msg") or 1)

    committed_items: List[Dict[str, Any]] = []
    approved_extra_items: List[Dict[str, Any]] = []

    for key in sorted(winning_facts.keys()):
        val = winning_facts[key]
        if key.startswith("budget.committed."):
            slug = key.split(".", 2)[2]
            amt = int(val)
            committed_items.append(
                {
                    "key": key,
                    "label": f"Committed: {_humanize_slug(slug)}",
                    "slug": slug,
                    "amount": amt,
                    "source_message": fact_msg_map.get(key, 1),
                }
            )
        elif key.startswith("budget.approved_extra."):
            slug = key.split(".", 2)[2]
            amt = int(val)
            approved_extra_items.append(
                {
                    "key": key,
                    "label": f"Approved Extra: {_humanize_slug(slug)}",
                    "slug": slug,
                    "amount": amt,
                    "source_message": fact_msg_map.get(key, 1),
                }
            )

    fixed_sum = sum(i["amount"] for i in committed_items) + sum(
        i["amount"] for i in approved_extra_items
    )
    honorarium = int(judging_res.get("honorarium_total", 0))

    def current_total() -> int:
        return int(venue_res.get("price", 0)) + int(food_res.get("cost", 0)) + honorarium + fixed_sum

    # Step 3(a): Downgrade food option if over cap and allowed
    if current_total() > cap and allow_food_downgrade and not food_res.get("override_used"):
        fallbacks = food_res.get("fallback_options") or []
        qty = int(food_res.get("quantity", 0))
        deliv = int(food_res.get("delivery_fee", 0))
        cur_price = int(food_res.get("unit_price", 0))
        for fb in fallbacks:
            if int(fb["unit_price"]) < cur_price:
                new_cost = qty * int(fb["unit_price"]) + deliv
                food_res["option"] = fb["slug"]
                food_res["slug"] = fb["slug"]
                food_res["name"] = fb["name"]
                food_res["unit_price"] = int(fb["unit_price"])
                food_res["cost"] = new_cost
                cur_price = int(fb["unit_price"])
                if trace:
                    trace.python_event(
                        "DOWNGRADE",
                        f"food downgraded to {fb['slug']} at Rs {fb['unit_price']}/head (cost Rs {new_cost})",
                    )
                if current_total() <= cap:
                    break

    # Step 3(b): Downgrade venue option if still over cap and allowed
    if current_total() > cap and allow_venue_downgrade and not venue_res.get("override_used"):
        fitting = venue_res.get("fitting_candidates") or []
        cur_v_price = int(venue_res.get("price", 0))
        for vc in fitting:
            if int(vc["price"]) < cur_v_price:
                venue_res["slug"] = vc["slug"]
                venue_res["name"] = vc["name"]
                venue_res["capacity"] = int(vc["capacity"])
                venue_res["price"] = int(vc["price"])
                cur_v_price = int(vc["price"])
                if trace:
                    trace.python_event(
                        "DOWNGRADE",
                        f"venue downgraded to {vc['name']} (Rs {vc['price']})",
                    )
                if current_total() <= cap:
                    break

    total = current_total()
    remaining = cap - total
    status = "ok" if total <= cap else "over_budget"
    overage = max(0, total - cap)

    v_slug = venue_res.get("slug") or "venue"
    f_slug = food_res.get("slug") or "food"

    items: List[Dict[str, Any]] = [
        {
            "label": f"Venue ({venue_res.get('name') or v_slug})",
            "amount": int(venue_res.get("price", 0)),
            "source_message": fact_msg_map.get(f"venue.option.{v_slug}.price", 1),
        },
        {
            "label": f"Food ({food_res.get('name') or f_slug} x {food_res.get('quantity', 0)})",
            "amount": int(food_res.get("cost", 0)),
            "source_message": fact_msg_map.get(f"food.option.{f_slug}.unit_price", 1),
        },
        {
            "label": f"Judging Honorarium ({judging_res.get('engaged', 0)} judges)",
            "amount": honorarium,
            "source_message": fact_msg_map.get("judging.rate", 1),
        },
    ]
    for ci in committed_items:
        items.append(
            {
                "label": ci["label"],
                "amount": ci["amount"],
                "source_message": ci["source_message"],
            }
        )
    for ai in approved_extra_items:
        items.append(
            {
                "label": ai["label"],
                "amount": ai["amount"],
                "source_message": ai["source_message"],
            }
        )

    warnings: List[str] = []
    if status == "over_budget":
        warnings.append(f"Total Rs {total} exceeds budget cap Rs {cap} by Rs {overage}")

    return {
        "status": status,
        "overage": overage,
        "cap": cap,
        "total": total,
        "remaining": remaining,
        "committed_total": sum(i["amount"] for i in committed_items),
        "approved_extra_total": sum(i["amount"] for i in approved_extra_items),
        "items": items,
        "warnings": warnings,
    }
