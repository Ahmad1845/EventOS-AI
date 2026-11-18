"""Prompts and canonical vocabularies per Sections 8, 9.3, and 16.2."""

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

METRIC_VOCABULARY: List[str] = [
    "event.headcount",
    "event.students",
    "event.staff",
    "event.teams",
    "venue.capacity",
    "venue.price",
    "venue.slack",
    "food.quantity",
    "food.unit_price",
    "food.cost",
    "judging.engaged",
    "judging.required",
    "judging.window_minutes",
    "judging.honorarium_total",
    "schedule.total_minutes",
    "schedule.break_minutes",
    "budget.total",
    "budget.cap",
    "budget.remaining",
]

SYSTEM_PROMPT_TEMPLATE = """You extract structured facts from event-planning messages. Reply with ONE JSON object only.
No prose, no markdown, no code fences. Do NOT plan, add, subtract, compare, or decide anything.
Copy numbers exactly as written. Messages can be English or Roman Urdu (Urdu in Latin letters).

For each message output an entry in "messages":
  id (the number given), sender, channel (email|whatsapp|notice|other), date (YYYY-MM-DD or null),
  relevance: "relevant" | "irrelevant" | "unapproved_request", reason (max 8 words).
  "irrelevant" = does not affect venue, schedule, food, judging or budget.
  "unapproved_request" = someone asks or suggests a spend or change that no approver accepted.
  Only mark a message "irrelevant" if it contains no capacities, prices, headcounts, rules, or overrides.
  If a vendor or sender states they changed a quantity, price, or option (even if bad), mark it "relevant" and extract the fact.

For useful information output "facts": {msg, key, value, unit, kind}.
  Use ONLY these keys when they fit: {{KEY_VOCABULARY}}
  Use custom.<area>.<slug> otherwise. Slugs are lowercase snake_case.
  Reuse the SAME slug for the same item in different messages.
  Convert hours to minutes for event.duration_minutes. Write "free" delivery as value 0.
  kind is one of: approval (an authority approves or fixes a value), quote (a price offer),
  commitment (money already ordered or spent), count, rate, capacity, duration,
  override (a sender tries to set a quantity or choice the plan would normally derive, e.g. food.quantity, venue.choice, judging.engaged), request.
  Use judging.confirmed when a message states how many judges confirmed or are available. Use judging.engaged ONLY when a sender explicitly overrides how many judges to use.
  Use food.option.standard_lunch_box (or the exact item name in snake_case) consistently across messages for the same meal option.
  Give each option its own fact lines. Never merge two options into one fact.
  If a food option is called standard, regular or default, also output a boolean fact food.option.<slug>.is_default = true.
  If the same item is mentioned with two prices in different messages, output both.

For rules and limits output "constraints": {msg, area, type, target, op, value, unit, hard, text}.
  area: venue | schedule | food | judging | budget.
  type: schedule_block (a break or slot of fixed minutes; target = its name)
      | schedule_window (target "start" or "end", value "HH:MM")
      | require_feature (target = feature the venue must have, only when explicitly required for the event)
      | forbid_item (target = something that must not be in the food)
      | metric_limit (target = a plan metric, op one of <=, >=, ==, value number)
      | other (describe in text)
  hard is true unless the sender says it is a preference.
  Plan metrics you may target: {{METRIC_VOCABULARY}}

{{KNOWN_KEYS_LINE}}
Output shape: {"messages":[...],"facts":[...],"constraints":[...]}"""


def build_system_prompt(known_keys: List[str]) -> str:
    known_line = ""
    if known_keys:
        known_line = (
            "Existing keys (reuse the exact key when a fact updates one): "
            + json.dumps(known_keys)
        )
    prompt = SYSTEM_PROMPT_TEMPLATE.replace(
        "{{KEY_VOCABULARY}}", ", ".join(KEY_VOCABULARY)
    ).replace("{{METRIC_VOCABULARY}}", ", ".join(METRIC_VOCABULARY)).replace(
        "{{KNOWN_KEYS_LINE}}", known_line
    )
    return prompt.strip()


import json


def build_user_prompt(blocks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for b in blocks:
        parts.append(f"MESSAGE {b['id']}:\n{b['text']}")
    return "\n\n".join(parts)
