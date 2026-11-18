"""Extractor module: calls LLM, repairs/parses JSON, normalizes values and checks grounding per Section 9."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.llm import LLMClient, LLMError
from core.prompts import build_system_prompt, build_user_prompt
from core.trace import Trace


class ExtractionFailed(Exception):
    pass


VALID_AREAS = {"venue", "schedule", "food", "judging", "budget"}
VALID_RELEVANCE = {"relevant", "irrelevant", "unapproved_request"}
VALID_FACT_KINDS = {
    "approval",
    "quote",
    "commitment",
    "count",
    "rate",
    "capacity",
    "duration",
    "override",
    "request",
}
VALID_CONSTRAINT_TYPES = {
    "schedule_block",
    "schedule_window",
    "require_feature",
    "forbid_item",
    "metric_limit",
    "other",
}

WORD_NUMBERS: Dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

WORD_MULTIPLIERS: Dict[str, int] = {
    "hundred": 10 ** 2,
    "thousand": 10 ** 3,
    "lakh": 10 ** 5,
    "lac": 10 ** 5,
}


def strip_and_find_json(raw: str) -> str:
    """Strip code fences and leading/trailing prose; return outermost JSON object string."""
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return cleaned
    return cleaned[start : end + 1]


def to_snake_slug(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def normalize_key(key: str) -> str:
    parts = [to_snake_slug(p) for p in str(key).strip().lower().split(".") if p.strip()]
    return ".".join(parts)


def _words_to_number(text: str) -> Optional[int]:
    tokens = re.findall(r"[a-z]+", text.lower())
    if not tokens:
        return None
    total = 0
    current = 0
    matched = False
    for tok in tokens:
        if tok in WORD_NUMBERS:
            current += WORD_NUMBERS[tok]
            matched = True
        elif tok in WORD_MULTIPLIERS:
            mult = WORD_MULTIPLIERS[tok]
            current = (current if current > 0 else 1) * mult
            if mult >= (10 ** 3):
                total += current
                current = 0
            matched = True
        elif tok in ("and", "a"):
            continue
        else:
            return None
    if not matched:
        return None
    return total + current


def normalize_value(val: Any, key: str = "", unit: Optional[str] = None) -> Any:
    """Normalize numeric strings, currency words, k/lakh suffixes, and English number words."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        if key == "event.duration_minutes" and unit and "hour" in str(unit).lower():
            return int(round(val * 60))
        if isinstance(val, float) and val.is_integer():
            return int(val)
        return val

    if not isinstance(val, str):
        return val

    s = val.strip()
    low = s.lower()

    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("free", "nil", "none") and ("fee" in key or "price" in key or "cost" in key):
        return 0

    # Preserve clock time HH:MM
    if re.match(r"^\d{1,2}:\d{2}$", s):
        return s

    # Strip currency prefixes/suffixes and commas
    cleaned = re.sub(r"\b(?:rs\.?|pkr|rupees?)\b", "", low, flags=re.IGNORECASE).strip()
    cleaned = cleaned.replace(",", "")

    # Check hours -> minutes if event.duration_minutes
    hr_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)$", cleaned)
    if hr_match and key == "event.duration_minutes":
        num = float(hr_match.group(1)) * 60
        return int(round(num))

    # Check k / thousand / lakh / lac suffixes (e.g., 10k, 1.5 lakh)
    k_match = re.match(r"^(-?\d+(?:\.\d+)?)\s*k$", cleaned)
    if k_match:
        num = float(k_match.group(1)) * (10 ** 3)
        return int(num) if num.is_integer() else num

    lakh_match = re.match(r"^(-?\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?)$", cleaned)
    if lakh_match:
        num = float(lakh_match.group(1)) * (10 ** 5)
        return int(num) if num.is_integer() else num

    # Direct numeric string (optionally followed by unit like 'minutes', 'seats', 'per head', '%')
    num_match = re.match(
        r"^(-?\d+(?:\.\d+)?)\s*(?:%|percent|minutes?|mins?|seats?|people|students?|teams?|judges?|boxes|per\s+head|each)?$",
        cleaned,
    )
    if num_match:
        num = float(num_match.group(1))
        if key == "event.duration_minutes" and unit and "hour" in str(unit).lower() and num <= 24:
            num = num * 60
        return int(num) if num.is_integer() else num

    # English number words
    word_num = _words_to_number(cleaned)
    if word_num is not None:
        if key == "event.duration_minutes" and ("hour" in low or (unit and "hour" in str(unit).lower())):
            return word_num * 60
        return word_num

    # If venue.choice is a slug
    if key == "venue.choice":
        return to_snake_slug(s)

    return s


def check_grounding(num_val: float, raw_message: str, key: str = "") -> bool:
    """Confirm numeric fact appears in the normalized source message (warning only)."""
    if num_val == 0 and re.search(r"\b(?:free|zero|nil|no\s+charge)\b", raw_message, re.IGNORECASE):
        return True

    msg_clean = raw_message.replace(",", "").lower()
    int_val = int(round(num_val))

    # Direct integer or float appearance
    if str(int_val) in msg_clean or str(num_val) in msg_clean:
        return True

    # Check hours conversion to minutes
    if key == "event.duration_minutes" and int_val % 60 == 0:
        hrs = int_val // 60
        if str(hrs) in msg_clean or any(
            w in msg_clean for w, v in WORD_NUMBERS.items() if v == hrs
        ):
            return True

    # Check k / lakh shorthand in message
    if int_val >= (10 ** 3) and int_val % (10 ** 3) == 0:
        k_val = int_val // (10 ** 3)
        if f"{k_val}k" in msg_clean or f"{k_val} thousand" in msg_clean:
            return True
    if int_val >= (10 ** 5) and int_val % (10 ** 4) == 0:
        lakh_val = num_val / (10 ** 5)
        lakh_str = str(int(lakh_val)) if lakh_val.is_integer() else str(lakh_val)
        if f"{lakh_str} lakh" in msg_clean or f"{lakh_str} lac" in msg_clean:
            return True

    # Check English number words in message
    for word, w_val in WORD_NUMBERS.items():
        if w_val == int_val and re.search(rf"\b{word}\b", msg_clean):
            return True

    return False


class Extractor:
    def __init__(self, llm_client: LLMClient, trace: Trace) -> None:
        self.llm = llm_client
        self.trace = trace
        self.call_counter = 0

    def _invoke(self, sys_prompt: str, usr_prompt: str) -> Dict[str, Any]:
        self.call_counter += 1
        call_num = self.call_counter
        full_input = f"[SYSTEM]\n{sys_prompt}\n\n[USER]\n{usr_prompt}"
        try:
            res = self.llm.call(sys_prompt, usr_prompt, tag="reading")
        except LLMError as e:
            raise ExtractionFailed(f"LLM request failed: {e}") from e

        self.trace.record_model_call(
            n=call_num,
            model=res.model,
            tag="reading",
            input_text=full_input,
            output_text=res.text,
            input_tokens=res.input_tokens,
            output_tokens=res.output_tokens,
            total_tokens=res.total_tokens,
        )
        json_text = strip_and_find_json(res.text)
        return json.loads(json_text)

    def run(
        self, blocks: List[Dict[str, Any]], known_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        sys_prompt = build_system_prompt(known_keys or [])
        usr_prompt = build_user_prompt(blocks)

        parsed: Optional[Dict[str, Any]] = None
        try:
            parsed = self._invoke(sys_prompt, usr_prompt)
        except json.JSONDecodeError:
            # Section 9.5: On failure do ONE retry call with original input + appended line
            retry_usr = (
                usr_prompt
                + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                "The output must be valid JSON only, with no markdown fences or extra text."
            )
            try:
                parsed = self._invoke(sys_prompt, retry_usr)
            except Exception as e:
                raise ExtractionFailed(f"Invalid JSON after retry: {e}") from e
        except ExtractionFailed:
            raise
        except Exception as e:
            raise ExtractionFailed(f"Extraction error: {e}") from e

        if not isinstance(parsed, dict):
            raise ExtractionFailed("Extractor output root is not a JSON object")

        block_map = {b["id"]: b["text"] for b in blocks}
        raw_messages = (
            parsed.get("m")
            if isinstance(parsed.get("m"), list)
            else (parsed.get("messages") if isinstance(parsed.get("messages"), list) else [])
        )
        raw_facts = (
            parsed.get("f")
            if isinstance(parsed.get("f"), list)
            else (parsed.get("facts") if isinstance(parsed.get("facts"), list) else [])
        )
        raw_constraints = (
            parsed.get("c")
            if isinstance(parsed.get("c"), list)
            else (parsed.get("constraints") if isinstance(parsed.get("constraints"), list) else [])
        )

        # Normalize messages
        clean_messages: List[Dict[str, Any]] = []
        seen_ids = set()
        for m in raw_messages:
            if not isinstance(m, dict):
                continue
            try:
                m_id = int(m.get("id", m.get("i", 0)))
            except Exception:
                continue
            if m_id <= 0:
                continue
            seen_ids.add(m_id)
            rel = str(m.get("rel", m.get("relevance", "relevant"))).strip().lower()
            if rel not in VALID_RELEVANCE:
                rel = "relevant"
            raw_d = m.get("d", m.get("date"))
            raw_reason = str(m.get("reason") or "").strip()
            if not raw_reason:
                if rel == "irrelevant":
                    raw_reason = "no planning impact"
                elif rel == "unapproved_request":
                    raw_reason = "unapproved request"
                else:
                    raw_reason = "facts extracted"
            clean_messages.append(
                {
                    "id": m_id,
                    "sender": str(m.get("s") or m.get("sender") or "Unknown").strip(),
                    "channel": str(m.get("ch") or m.get("channel") or "other").strip().lower(),
                    "date": str(raw_d).strip() if raw_d else None,
                    "relevance": rel,
                    "reason": raw_reason,
                }
            )

        # Ensure every input block has a message metadata entry
        for b in blocks:
            if b["id"] not in seen_ids:
                clean_messages.append(
                    {
                        "id": b["id"],
                        "sender": "Unknown",
                        "channel": "other",
                        "date": None,
                        "relevance": "relevant",
                        "reason": "facts extracted",
                    }
                )
        clean_messages.sort(key=lambda x: x["id"])

        # Normalize facts
        clean_facts: List[Dict[str, Any]] = []
        for f in raw_facts:
            if not isinstance(f, dict):
                continue
            raw_key = f.get("k", f.get("key"))
            raw_val = f.get("v", f.get("value"))
            if raw_key is None or str(raw_key).strip() == "" or raw_val is None or str(raw_val).strip() == "":
                self.trace.python_event("EXTRACT", f"dropped incomplete fact: {f}")
                continue
            try:
                msg_id = int(f.get("m", f.get("msg", 1)))
            except Exception:
                msg_id = 1

            norm_k = normalize_key(str(raw_key))
            raw_u = f.get("u", f.get("unit"))
            unit = str(raw_u).strip() if raw_u is not None else None
            norm_v = normalize_value(raw_val, key=norm_k, unit=unit)
            if norm_k.endswith(".feature") and isinstance(norm_v, str):
                norm_v = to_snake_slug(norm_v)

            kind = str(f.get("kd", f.get("kind")) or "count").strip().lower()
            if kind not in VALID_FACT_KINDS:
                kind = "count"

            src_text = block_map.get(msg_id, "")
            if norm_k == "judging.engaged" and kind != "override" and "confirm" in src_text.lower():
                norm_k = "judging.confirmed"

            grounded = True
            if isinstance(norm_v, (int, float)) and not isinstance(norm_v, bool):
                grounded = check_grounding(float(norm_v), src_text, key=norm_k)
                if not grounded:
                    self.trace.python_event(
                        "WARNING",
                        f"ungrounded numeric fact {norm_k}={norm_v} in message {msg_id}",
                    )

            clean_facts.append(
                {
                    "msg": msg_id,
                    "key": norm_k,
                    "value": norm_v,
                    "unit": unit,
                    "kind": kind,
                    "grounded": grounded,
                }
            )

        # Normalize constraints
        clean_constraints: List[Dict[str, Any]] = []
        for c in raw_constraints:
            if not isinstance(c, dict):
                continue
            area = str(c.get("a", c.get("area")) or "").strip().lower()
            ctype = str(c.get("t", c.get("type")) or "").strip().lower()
            if area not in VALID_AREAS or ctype not in VALID_CONSTRAINT_TYPES:
                self.trace.python_event("EXTRACT", f"dropped invalid constraint: {c}")
                continue
            try:
                msg_id = int(c.get("m", c.get("msg", 1)))
            except Exception:
                msg_id = 1
            target = str(c.get("tg", c.get("target")) or "").strip()
            if ctype == "metric_limit":
                target = normalize_key(target)
            elif ctype in ("require_feature", "forbid_item", "schedule_block"):
                target = to_snake_slug(target) if target else "item"

            c_raw_u = c.get("u", c.get("unit"))
            c_unit = str(c_raw_u).strip() if c_raw_u is not None else None
            c_raw_v = c.get("v", c.get("value"))
            c_val = normalize_value(c_raw_v, key=target, unit=c_unit)
            hard = bool(c.get("h", c.get("hard", True)))
            c_op = c.get("op")
            c_txt = c.get("tx", c.get("text"))
            clean_constraints.append(
                {
                    "msg": msg_id,
                    "area": area,
                    "type": ctype,
                    "target": target,
                    "op": str(c_op).strip() if c_op else None,
                    "value": c_val,
                    "unit": c_unit,
                    "hard": hard,
                    "text": str(c_txt or "").strip(),
                }
            )

        irr_count = sum(1 for m in clean_messages if m["relevance"] == "irrelevant")
        unapp_count = sum(1 for m in clean_messages if m["relevance"] == "unapproved_request")
        self.trace.python_event(
            "EXTRACT",
            f"{len(clean_facts)} facts, {len(clean_constraints)} constraints, "
            f"{irr_count} irrelevant, {unapp_count} unapproved_request",
        )

        return {
            "messages": clean_messages,
            "facts": clean_facts,
            "constraints": clean_constraints,
        }
