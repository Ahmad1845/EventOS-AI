"""Venue solver per Section 15.3."""

from typing import Any, Dict, List, Optional, Set


def _humanize_slug(slug: str) -> str:
    parts = slug.split("_")
    out: List[str] = []
    for p in parts:
        if len(p) == 1 and p.isalpha():
            out.append(p.upper())
        else:
            out.append(p.capitalize())
    return " ".join(out)


FEATURE_SYNONYM_GROUPS = [
    {
        "step_free",
        "step_free_access",
        "ramp",
        "ramp_access",
        "wheelchair",
        "wheelchair_access",
        "ground_floor",
        "ground_floor_ramp_access",
        "elevator",
        "lift",
        "accessible",
        "accessibility",
    },
    {
        "generator",
        "standby_generator",
        "backup_power",
        "power_backup",
        "ups",
        "solar",
    },
]


def feature_matches(req_feat: str, option_features: List[str]) -> bool:
    req = req_feat.strip().lower().replace(" ", "_").replace("-", "_")
    req_tokens = {t for t in req.split("_") if t}
    req_groups = [
        idx
        for idx, grp in enumerate(FEATURE_SYNONYM_GROUPS)
        if req in grp or any(t in grp for t in req_tokens) or any(g in req for g in grp)
    ]

    for of in option_features:
        of_norm = str(of).strip().lower().replace(" ", "_").replace("-", "_")
        if req == of_norm or req in of_norm or of_norm in req:
            return True
        if req_groups:
            of_tokens = {t for t in of_norm.split("_") if t}
            for idx in req_groups:
                grp = FEATURE_SYNONYM_GROUPS[idx]
                if of_norm in grp or any(t in grp for t in of_tokens) or any(g in of_norm for g in grp):
                    return True
    return False


def _feature_matches(req_feat: str, option_features: List[str]) -> bool:
    return feature_matches(req_feat, option_features)


def extract_venue_options(winning_facts: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    options: Dict[str, Dict[str, Any]] = {}
    for key, val in winning_facts.items():
        if not key.startswith("venue.option."):
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
                "capacity": None,
                "price": None,
                "features": [],
                "available": True,
            },
        )
        if field == "capacity":
            try:
                opt["capacity"] = int(val)
            except Exception:
                pass
        elif field == "price":
            try:
                opt["price"] = int(val)
            except Exception:
                pass
        elif field == "available":
            if isinstance(val, bool):
                opt["available"] = val
            else:
                low = str(val).strip().lower()
                opt["available"] = low not in ("false", "0", "no", "unavailable", "closed", "maintenance")
        elif field == "feature":
            raw_items = val if isinstance(val, list) else str(val).split(",")
            for item in raw_items:
                clean_item = str(item).strip()
                if clean_item and clean_item not in opt["features"]:
                    opt["features"].append(clean_item)
    return options


def solve_venue(
    headcount: int,
    winning_facts: Dict[str, Any],
    constraints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    options_map = extract_venue_options(winning_facts)
    if not options_map:
        return {
            "status": "missing",
            "missing_keys": ["venue.option.*"],
            "slug": None,
            "name": None,
            "capacity": 0,
            "price": 0,
            "slack": 0,
            "features": [],
            "rejected_options": [],
            "skipped_fitting": [],
            "fitting_candidates": [],
            "warnings": ["No venue options found"],
        }

    req_features: List[str] = []
    forbidden_venues: List[str] = []
    for c in constraints:
        if c.get("area") == "venue" and c.get("type") == "require_feature" and c.get("hard", True):
            target = str(c.get("target") or "").strip().lower()
            if target and target not in req_features:
                req_features.append(target)
        elif c.get("area") == "venue" and c.get("type") == "forbid_item" and c.get("hard", True):
            target = str(c.get("target") or "").strip().lower().replace(" ", "_")
            if target and target not in forbidden_venues:
                forbidden_venues.append(target)

    candidates: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for slug in sorted(options_map.keys()):
        opt = options_map[slug]
        cap = opt["capacity"]
        price = opt["price"]
        feats = opt["features"]
        avail = bool(opt.get("available", True))

        if cap is None:
            rejected.append(
                {
                    "slug": slug,
                    "name": opt["name"],
                    "capacity": None,
                    "price": price,
                    "reason": "missing capacity",
                }
            )
            continue
        if price is None:
            rejected.append(
                {
                    "slug": slug,
                    "name": opt["name"],
                    "capacity": cap,
                    "price": None,
                    "reason": "missing price",
                }
            )
            continue

        reasons: List[str] = []
        if not avail or any(fv == slug or fv in slug or slug in fv for fv in forbidden_venues):
            reasons.append("unavailable / under maintenance")
        if cap < headcount:
            reasons.append(f"capacity {cap} < {headcount}")
        for rf in req_features:
            if not feature_matches(rf, feats):
                reasons.append(f"missing feature {rf}")

        if reasons:
            rejected.append(
                {
                    "slug": slug,
                    "name": opt["name"],
                    "capacity": cap,
                    "price": price,
                    "reason": ", ".join(reasons),
                }
            )
        else:
            candidates.append(opt)

    # Sort fitting candidates by lowest price, then smaller capacity, then slug order
    candidates.sort(key=lambda x: (x["price"], x["capacity"], x["slug"]))

    override_slug = winning_facts.get("venue.choice")
    if override_slug is not None:
        ov_slug = str(override_slug).strip().lower().replace(" ", "_")
        chosen = options_map.get(ov_slug)
        if chosen and chosen["capacity"] is not None and chosen["price"] is not None:
            skipped_fitting = [
                {
                    "slug": c["slug"],
                    "name": c["name"],
                    "capacity": c["capacity"],
                    "price": c["price"],
                    "reason": f"fits ({c['capacity']} seats) but not selected due to venue override",
                }
                for c in candidates
                if c["slug"] != chosen["slug"]
            ]
            return {
                "status": "ok",
                "slug": chosen["slug"],
                "name": chosen["name"],
                "capacity": chosen["capacity"],
                "price": chosen["price"],
                "slack": chosen["capacity"] - headcount,
                "features": chosen["features"],
                "rejected_options": [r for r in rejected if r["slug"] != chosen["slug"]],
                "skipped_fitting": skipped_fitting,
                "fitting_candidates": candidates,
                "override_used": True,
                "warnings": [],
            }

    if not candidates:
        return {
            "status": "no_fit",
            "slug": None,
            "name": None,
            "capacity": 0,
            "price": 0,
            "slack": 0,
            "features": [],
            "rejected_options": rejected,
            "skipped_fitting": [],
            "fitting_candidates": [],
            "warnings": ["No venue option satisfies capacity and feature requirements"],
        }

    chosen = candidates[0]
    skipped_fitting = [
        {
            "slug": c["slug"],
            "name": c["name"],
            "capacity": c["capacity"],
            "price": c["price"],
            "reason": f"fits ({c['capacity']} seats) but costs more (Rs {c['price']} vs Rs {chosen['price']})",
        }
        for c in candidates[1:]
    ]
    return {
        "status": "ok",
        "slug": chosen["slug"],
        "name": chosen["name"],
        "capacity": chosen["capacity"],
        "price": chosen["price"],
        "slack": chosen["capacity"] - headcount,
        "features": chosen["features"],
        "rejected_options": rejected,
        "skipped_fitting": skipped_fitting,
        "fitting_candidates": candidates,
        "override_used": False,
        "warnings": [],
    }
