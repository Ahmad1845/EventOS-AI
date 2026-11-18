"""Lean prompts and canonical key vocabulary per Sections 8, 9.3, and 16.2."""

from typing import Any, Dict, List


KEY_VOCABULARY: List[str] = [
    "event.students",
    "event.team_size",
    "event.teams",
    "event.staff",
    "event.duration_minutes",
    "event.start_time",
    "budget.cap",
    "budget.committed.<slug>",
    "budget.approved_extra.<slug>",
    "budget.request.<slug>",
    "venue.option.<slug>.capacity",
    "venue.option.<slug>.price",
    "venue.option.<slug>.feature",
    "venue.choice",
    "food.option.<slug>.unit_price",
    "food.option.<slug>.is_default",
    "food.delivery_fee",
    "food.quantity",
    "judging.confirmed",
    "judging.rate",
    "judging.minutes_per_team",
    "judging.max_teams_per_judge",
    "judging.engaged",
    "custom.<area>.<slug>",
]

SYSTEM_PROMPT_TEMPLATE = """Extract event facts into ONE valid JSON object (no markdown/prose). Never plan or calculate. Copy numbers verbatim. English or Roman Urdu.
Keys: {{KEY_VOCABULARY}}. Slugs: lowercase snake_case, consistent across messages. Hours->minutes for event.duration_minutes; free delivery=0.

Schema:
{"m":[{"id":1,"s":"sender","ch":"email|whatsapp|notice|other","d":"MM-DD","rel":"relevant|irrelevant|unapproved_request"}],"f":[{"m":1,"k":"key","v":0,"u":"unit","kd":"approval|quote|commitment|count|rate|capacity|duration|override|request"}],"c":[{"m":1,"a":"venue|schedule|food|judging|budget","t":"schedule_block|schedule_window|require_feature|forbid_item|metric_limit|other","tg":"target","op":"<=|>=|==","v":0,"h":true,"tx":"rule"}]}

Rules:
- Minified single-line JSON (no spaces/newlines). Omit null/empty fields ("u","d","op"). Always emit one "m" entry per msg.
- Emit facts in "f" for EVERY price, quote, capacity, count, or bill in EVERY msg—even when a later msg updates the same item.
- rel="irrelevant" ONLY for chitchat/late-arrival notes with zero facts; "unapproved_request"=unapproved ask.
- budget.committed.<slug>=vendor bills/invoices/ordered costs; budget.approved_extra.<slug>=approved extras; budget.request.<slug>=unapproved asks.
- kd="override" if setting derived values (food.quantity, venue.choice, judging.engaged). Confirmed judges="judging.confirmed" (not engaged).
- Separate facts per option. Default/standard/regular food gets food.option.<slug>.is_default=true.
- Constraints: schedule_block (tg=name, v=minutes), schedule_window (tg=start|end, v=HH:MM), require_feature (only if explicitly required), forbid_item, metric_limit."""


def build_system_prompt(known_keys: List[str]) -> str:
    # known_keys intentionally omitted to keep prompts lean; Python fuzzy_match_key handles aliases
    _ = known_keys
    return SYSTEM_PROMPT_TEMPLATE.replace("{{KEY_VOCABULARY}}", ", ".join(KEY_VOCABULARY)).strip()


def build_user_prompt(blocks: List[Dict[str, Any]]) -> str:
    return "\n".join(f"[{b['id']}] {b['text']}" for b in blocks)
