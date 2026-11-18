"""Fact Store module: date parsing, fuzzy slug matching, conflict resolution, and protected facts per Section 13."""

import datetime
import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.trace import Trace


PROTECTED_KEYS: Set[str] = {
    "event.students",
    "event.duration_minutes",
    "budget.cap",
    "event.staff",
    "event.team_size",
}

MONTH_MAP: Dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class ProtectedFactViolation(Exception):
    def __init__(self, key: str, approved_by: str, attempted_by: str) -> None:
        self.key = key
        self.approved_by = approved_by
        self.attempted_by = attempted_by
        super().__init__(
            f"Rejected: {key} was approved by {approved_by}; {attempted_by} cannot change it"
        )


def detect_pack_year(texts: List[str], fallback_year: Optional[int] = None) -> int:
    """Detect explicit 4-digit year (20xx) from raw pack texts; fallback to system clock year."""
    for txt in texts:
        m = re.search(r"\b(20\d{2})\b", str(txt or ""))
        if m:
            return int(m.group(1))
    return fallback_year if fallback_year is not None else datetime.date.today().year


def parse_message_date(raw_date: Optional[str], default_year: Optional[int] = None) -> Optional[str]:
    """Parse day and month only, ignoring any year guessed by the model; use pack/system year."""
    if not raw_date:
        return None
    s = str(raw_date).strip()
    if not s or s.lower() == "null":
        return None

    year = default_year if default_year is not None else datetime.date.today().year

    # Match YYYY-MM-DD (ignore YYYY from model, keep MM-DD)
    m_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m_iso:
        mo, d = int(m_iso.group(2)), int(m_iso.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"

    # Match MM-DD or MM/DD
    m_md = re.match(r"^(\d{1,2})[-/](\d{1,2})$", s)
    if m_md:
        mo, d = int(m_md.group(1)), int(m_md.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"

    # Match DD Mon [YYYY] (ignore optional year from model)
    m_dmy = re.match(r"^(\d{1,2})\s+([A-Za-z]+)(?:\s+\d{4})?$", s)
    if m_dmy:
        d = int(m_dmy.group(1))
        mo_str = m_dmy.group(2).lower()
        mo = MONTH_MAP.get(mo_str[:3])
        if mo and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"

    # Match Mon DD [YYYY] (ignore optional year from model)
    m_mdy = re.match(r"^([A-Za-z]+)\s+(\d{1,2})(?:,?\s*\d{4})?$", s)
    if m_mdy:
        mo_str = m_mdy.group(1).lower()
        d = int(m_mdy.group(2))
        mo = MONTH_MAP.get(mo_str[:3])
        if mo and 1 <= d <= 31:
            return f"{year:04d}-{mo:02d}-{d:02d}"

    return None


def _split_key_for_fuzzy(key: str) -> Optional[Tuple[str, str, str]]:
    """
    Split a key into (prefix, slug, suffix) for fuzzy matching per Section 13.3.
    Examples:
      venue.option.hall_a.price -> ('venue.option', 'hall_a', 'price')
      food.option.standard_lunch_box.unit_price -> ('food.option', 'standard_lunch_box', 'unit_price')
      budget.committed.printing -> ('budget.committed', 'printing', '')
      custom.venue.generator -> ('custom.venue', 'generator', '')
    """
    parts = key.split(".")
    if len(parts) == 4 and parts[1] == "option":
        return f"{parts[0]}.{parts[1]}", parts[2], parts[3]
    if len(parts) == 3 and parts[0] in ("budget", "custom"):
        return f"{parts[0]}.{parts[1]}", parts[2], ""
    return None


def _has_distinct_designator(s1: str, s2: str) -> bool:
    """Return True if two slugs have different designators like hall_a vs hall_b or basic vs standard."""
    t1 = s1.split("_")
    t2 = s2.split("_")
    distinct_words = {
        "north",
        "south",
        "east",
        "west",
        "alpha",
        "beta",
        "gamma",
        "delta",
        "basic",
        "standard",
        "economy",
        "lite",
        "vip",
        "premium",
        "deluxe",
    }
    diff_tokens = set(t1) ^ set(t2)
    if diff_tokens & distinct_words:
        return True
    if t1 and t2 and t1[-1] != t2[-1]:
        if len(t1[-1]) == 1 or len(t2[-1]) == 1 or t1[-1].isdigit() or t2[-1].isdigit():
            return True
    return False


def fuzzy_match_key(
    new_key: str,
    existing_facts: List[Dict[str, Any]],
    current_seq: Optional[int] = None,
    trace: Optional[Trace] = None,
) -> str:
    """Compare new key to existing keys with same prefix using SequenceMatcher >= 0.8 or token subset."""
    existing_keys = {f["key"] for f in existing_facts if f.get("key")}
    if new_key in existing_keys:
        return new_key

    parsed = _split_key_for_fuzzy(new_key)
    if not parsed:
        return new_key
    prefix, slug, suffix = parsed

    # Do not merge against options introduced in the exact same message
    same_msg_slugs = set()
    if current_seq is not None:
        for ef in existing_facts:
            if ef.get("seq") == current_seq and ef.get("key"):
                ep = _split_key_for_fuzzy(ef["key"])
                if ep and ep[0] == prefix:
                    same_msg_slugs.add(ep[1])

    best_slug: Optional[str] = None
    best_ratio = 0.0
    slug_tokens = set(slug.split("_"))

    for ek in sorted(existing_keys):
        ep = _split_key_for_fuzzy(ek)
        if not ep:
            continue
        e_prefix, e_slug, _ = ep
        if e_prefix != prefix or e_slug in same_msg_slugs:
            continue
        if _has_distinct_designator(slug, e_slug):
            continue
        ratio = difflib.SequenceMatcher(None, slug, e_slug).ratio()
        e_tokens = set(e_slug.split("_"))
        is_subset = bool(slug_tokens and e_tokens and (slug_tokens <= e_tokens or e_tokens <= slug_tokens))
        effective_score = max(ratio, 0.85) if is_subset else ratio
        if effective_score >= 0.8 and effective_score > best_ratio:
            best_ratio = effective_score
            best_slug = e_slug

    if best_slug and best_slug != slug:
        merged_key = f"{prefix}.{best_slug}.{suffix}" if suffix else f"{prefix}.{best_slug}"
        if trace:
            trace.python_event(
                "MERGE",
                f"fuzzy matched {new_key} -> {merged_key} (ratio {best_ratio:.2f})",
            )
        return merged_key

    return new_key


def sender_similarity(s1: str, s2: str) -> float:
    a = s1.strip().lower()
    b = s2.strip().lower()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def resolve_message_date(
    raw_date: Optional[str],
    existing_facts: List[Dict[str, Any]],
    existing_messages: List[Dict[str, Any]],
    mode: str,
    pack_year: Optional[int] = None,
) -> str:
    """Assign YYYY-MM-DD date per Section 13.1 using pack_year or system clock year."""
    parsed = parse_message_date(raw_date, default_year=pack_year)
    if parsed:
        return parsed

    known_dates = [
        m.get("resolved_date")
        for m in existing_messages
        if m.get("resolved_date")
    ]
    fact_dates = [f.get("date") for f in existing_facts if f.get("date")]
    all_dates = [d for d in (known_dates + fact_dates) if isinstance(d, str) and len(d) == 10]

    if mode == "fresh":
        if all_dates:
            return all_dates[-1]
    else:
        if all_dates:
            return max(all_dates)

    yr = pack_year if pack_year is not None else datetime.date.today().year
    return f"{yr:04d}-01-01"


def get_winning_facts(facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return dict of winning values for single-valued keys and list for multi-valued (.feature) keys."""
    result: Dict[str, Any] = {}
    for f in facts:
        if f.get("superseded_by") is not None:
            continue
        k = f["key"]
        v = f["value"]
        if k.endswith(".feature"):
            lst = result.setdefault(k, [])
            if v not in lst:
                lst.append(v)
        else:
            result[k] = v
    return result


def apply_message_to_store(
    message_meta: Dict[str, Any],
    msg_facts: List[Dict[str, Any]],
    msg_constraints: List[Dict[str, Any]],
    seq: int,
    resolved_date: str,
    candidate_facts: List[Dict[str, Any]],
    candidate_constraints: List[Dict[str, Any]],
    policy: Dict[str, Any],
    trace: Optional[Trace] = None,
) -> Set[str]:
    """
    Apply a single message's facts and constraints into candidate_facts and candidate_constraints.
    Returns the set of keys (and constraint area markers) whose winning value changed.
    Raises ProtectedFactViolation if an unauthorized sender tries to overwrite a protected fact.
    """
    relevance = message_meta.get("relevance", "relevant")
    sender = str(message_meta.get("sender") or "Unknown")
    reason = str(message_meta.get("reason") or "not applicable")

    if relevance == "irrelevant":
        if trace:
            trace.python_event("IGNORE", f"IGNORED message {seq} ({sender}): {reason}")
        return set()

    protect_enabled = bool(policy.get("protect_approved_facts", True))
    sender_threshold = float(policy.get("sender_match_threshold", 0.6))
    changed_keys: Set[str] = set()

    for raw_f in msg_facts:
        f = dict(raw_f)
        raw_key = str(f["key"])

        # If a relevant message (e.g. Finance bill update) is tagged budget.request.* or custom.budget.*,
        # check if it matches an already-committed or approved_extra budget key before rewriting.
        if relevance == "relevant" and (
            raw_key.startswith("budget.request.") or raw_key.startswith("custom.budget.")
        ):
            slug_part = raw_key.split(".", 2)[2]
            for target_prefix in ("budget.committed", "budget.approved_extra"):
                probe = f"{target_prefix}.{slug_part}"
                matched_probe = fuzzy_match_key(
                    probe, candidate_facts, current_seq=seq, trace=trace
                )
                if any(
                    ef.get("key") == matched_probe and ef.get("seq") != seq
                    for ef in candidate_facts
                ):
                    raw_key = matched_probe
                    f["kind"] = (
                        "commitment"
                        if target_prefix == "budget.committed"
                        else "approval"
                    )
                    break

        key = fuzzy_match_key(
            raw_key, candidate_facts, current_seq=seq, trace=trace
        )

        # If message is unapproved_request, rewrite key under budget.request.<slug>
        if relevance == "unapproved_request" or f.get("kind") == "request":
            if not key.startswith("budget.request."):
                slug = key.split(".")[-1]
                key = f"budget.request.{slug}"
            f["kind"] = "request"

        f["key"] = key
        f["seq"] = seq
        f["date"] = resolved_date
        f["sender"] = sender
        f["superseded_by"] = None

        # Multi-valued feature keys accumulate without conflict
        if key.endswith(".feature"):
            existing_vals = {
                ef["value"]
                for ef in candidate_facts
                if ef["key"] == key and ef.get("superseded_by") is None
            }
            candidate_facts.append(f)
            if f["value"] not in existing_vals:
                changed_keys.add(key)
            continue

        # Find current active winner for this key
        active_winners = [
            ef
            for ef in candidate_facts
            if ef["key"] == key and ef.get("superseded_by") is None
        ]

        if not active_winners:
            candidate_facts.append(f)
            changed_keys.add(key)
            continue

        winner = active_winners[-1]

        # Section 13.4: Check protected facts
        if protect_enabled and key in PROTECTED_KEYS and winner.get("kind") == "approval":
            orig_sender = str(winner.get("sender") or "Approver")
            if winner.get("value") != f["value"]:
                sim = sender_similarity(orig_sender, sender)
                if sim < sender_threshold:
                    raise ProtectedFactViolation(
                        key=key, approved_by=orig_sender, attempted_by=sender
                    )

        # Section 13.2: Conflict resolution (latest (date, seq) wins)
        win_tuple = (str(winner.get("date") or ""), int(winner.get("seq") or 0))
        new_tuple = (str(resolved_date), int(seq))

        if new_tuple >= win_tuple:
            old_val = winner.get("value")
            old_date = winner.get("date")
            winner["superseded_by"] = seq
            candidate_facts.append(f)
            if old_val != f["value"]:
                changed_keys.add(key)
                if trace:
                    trace.python_event(
                        "RESOLVE",
                        f"{key}: {old_val} ({old_date}) -> {f['value']} ({resolved_date}), later date wins",
                    )
        else:
            # Incoming fact is older than current winner; mark incoming as superseded immediately
            f["superseded_by"] = winner.get("seq")
            candidate_facts.append(f)
            if trace:
                trace.python_event(
                    "RESOLVE",
                    f"{key}: kept {winner.get('value')} ({winner.get('date')}) over older {f['value']} ({resolved_date})",
                )

    # Apply constraints for relevant messages
    if relevance == "relevant":
        for raw_c in msg_constraints:
            c = dict(raw_c)
            c["seq"] = seq
            c["date"] = resolved_date
            c["sender"] = sender
            candidate_constraints.append(c)
            c_area = str(c.get("area") or "schedule")
            changed_keys.add(f"constraint.{c_area}.{c.get('target', 'rule')}")

    return changed_keys
