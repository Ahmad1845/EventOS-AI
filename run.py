"""EventOS CLI entry point: python run.py <messages_file> per Sections 6, 12, and 18."""

import copy
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set

from core.extractor import ExtractionFailed, Extractor
from core.factstore import (
    ProtectedFactViolation,
    apply_message_to_store,
    detect_pack_year,
    resolve_message_date,
)
from core.ingest import ingest_file
from core.llm import LLMClient
from core.planner import build_plan
from core.render import format_terminal_output, write_outputs
from core.router import PLANNING_ORDER, affected_areas
from core.state import (
    STATE_PATH,
    archive_state,
    default_state,
    detect_session,
    get_known_keys,
    load_state,
    save_state,
)
from core.trace import Trace
from core.validator import validate_plan


def _infer_fallback_year(state: Dict[str, Any]) -> Optional[int]:
    for m in state.get("messages") or []:
        rd = str(m.get("resolved_date") or "")
        if len(rd) >= 4 and rd[:4].isdigit():
            return int(rd[:4])
    return None


def _refresh_message_statuses(
    messages: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
    constraints: List[Dict[str, Any]],
) -> None:
    """Assign one mutually exclusive status per message: rejected, ignored, excluded, superseded, or applied."""
    facts_by_seq: Dict[int, List[Dict[str, Any]]] = {}
    for f in facts:
        facts_by_seq.setdefault(int(f.get("seq") or 0), []).append(f)
    cons_by_seq: Dict[int, List[Dict[str, Any]]] = {}
    for c in constraints:
        cons_by_seq.setdefault(int(c.get("seq") or 0), []).append(c)

    for m in messages:
        cur_status = m.get("status")
        if cur_status in ("rejected", "ignored"):
            m.setdefault("superseded_by", [])
            continue

        seq = int(m.get("seq") or 0)
        meta = m.get("meta") or {}
        m_facts = facts_by_seq.get(seq, [])
        m_cons = cons_by_seq.get(seq, [])

        if meta.get("relevance") == "unapproved_request" or (
            m_facts and all(f.get("kind") == "request" for f in m_facts) and not m_cons
        ):
            m["status"] = "excluded"
            m["superseded_by"] = []
            m["status_detail"] = "Unapproved request (excluded from budget)"
            continue

        if m_facts and not m_cons and all(f.get("superseded_by") is not None for f in m_facts):
            sup_by = sorted(
                {int(f["superseded_by"]) for f in m_facts if f.get("superseded_by") is not None}
            )
            m["status"] = "superseded"
            m["superseded_by"] = sup_by
            m["status_detail"] = "Superseded by " + ", ".join(f"#{s}" for s in sup_by)
            continue

        m["status"] = "applied"
        m["superseded_by"] = []
        m["status_detail"] = "Applied to plan"



def load_config(path: str = "config.json") -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "llm": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "base_url": "",
            "api_key_env": "GEMINI_API_KEY",
            "temperature": 0,
            "max_output_tokens": 15 * (10 ** 2),
            "timeout_seconds": 80,
        },
        "policy": {
            "judges_engaged": "minimum_required",
            "opening_minutes": 15,
            "closing_minutes": 15,
            "build_split_before_breaks": 0.5,
            "protect_approved_facts": True,
            "exclude_unapproved_requests": True,
            "food_preference": "default_then_cheapest",
            "sender_match_threshold": 0.6,
        },
    }


def run_pipeline(
    filepath: str,
    config_path: str = "config.json",
    state_path: str = STATE_PATH,
    llm_override: Optional[Any] = None,
) -> int:
    """Execute EventOS pipeline for filepath. Never crashes; returns exit code 0."""
    t_start = time.monotonic()
    try:
        if not os.path.exists(filepath):
            print(f"Error: file not found: {filepath}")
            return 0

        blocks = ingest_file(filepath)
        if not blocks:
            print("no messages found")
            return 0

        config = load_config(config_path)
        policy = config.get("policy") or {}
        llm_client = llm_override if llm_override is not None else LLMClient(config.get("llm") or {})

        state = load_state(state_path)
        mode, new_blocks = detect_session(state, blocks)

        if mode == "new_pack":
            archive_state(state_path)
            state = default_state()
            mode = "fresh"
        elif state is None:
            state = default_state()
            mode = "fresh"

        if mode == "nothing_new":
            print("no new messages")
            existing_plan = state.get("plan")
            if existing_plan:
                existing_plan["tokens"] = {
                    "last_run": 0,
                    "session": int(state.get("session_tokens", 0)),
                }
                existing_plan["recomputed_areas"] = []
                trace = Trace(
                    run_number=int(state.get("runs", 0)) + 1,
                    mode="nothing_new",
                    filename=os.path.basename(filepath),
                    num_messages=0,
                )
                trace.python_event("SESSION", "no new messages; reusing existing plan")
                tr_text = trace.format_run_trace()
                term_out = format_terminal_output(tr_text, existing_plan, state, run_tokens=0)
                print(term_out)
            return 0

        run_number = int(state.get("runs", 0)) + 1
        trace = Trace(
            run_number=run_number,
            mode=mode,
            filename=os.path.basename(filepath),
            num_messages=len(new_blocks),
        )

        pack_year = detect_pack_year(
            [b["text"] for b in new_blocks], fallback_year=_infer_fallback_year(state)
        )
        known_keys: List[str] = []
        extractor = Extractor(llm_client, trace)

        try:
            extracted = extractor.run(new_blocks, known_keys=known_keys)
        except ExtractionFailed as e:
            trace.python_event("ERROR", f"Extraction failed: {e}. Plan unchanged.")
            tr_text = trace.format_run_trace()
            state["runs"] = run_number
            state["session_tokens"] = int(state.get("session_tokens", 0)) + trace.total_tokens
            tr_dict = trace.to_dict()
            tr_dict["formatted"] = tr_text
            state.setdefault("trace_history", []).append(tr_dict)
            save_state(state, state_path)
            if state.get("plan"):
                state["plan"]["tokens"] = {
                    "last_run": trace.total_tokens,
                    "session": state["session_tokens"],
                }
                term_out = write_outputs(state["plan"], state, tr_text, last_mode=mode)
                print(term_out)
            else:
                print(tr_text)
            return 0

        meta_by_id = {m["id"]: m for m in extracted["messages"]}
        facts_by_id: Dict[int, List[Dict[str, Any]]] = {}
        for f in extracted["facts"]:
            facts_by_id.setdefault(int(f["msg"]), []).append(f)
        constraints_by_id: Dict[int, List[Dict[str, Any]]] = {}
        for c in extracted["constraints"]:
            constraints_by_id.setdefault(int(c["msg"]), []).append(c)

        next_seq = len(state.get("messages", [])) + 1
        recomputed_union: Set[str] = set()

        if mode == "fresh":
            candidate_facts: List[Dict[str, Any]] = []
            candidate_constraints: List[Dict[str, Any]] = []
            candidate_messages: List[Dict[str, Any]] = []

            for b in new_blocks:
                bid = int(b["id"])
                seq = next_seq
                next_seq += 1
                meta = meta_by_id.get(
                    bid,
                    {
                        "id": bid,
                        "sender": "Unknown",
                        "channel": "other",
                        "date": None,
                        "relevance": "relevant",
                        "reason": "",
                    },
                )
                r_date = resolve_message_date(
                    meta.get("date"),
                    candidate_facts,
                    candidate_messages,
                    mode="fresh",
                    pack_year=pack_year,
                )
                m_facts = facts_by_id.get(bid, [])
                m_cons = constraints_by_id.get(bid, [])
                if meta.get("relevance") == "irrelevant":
                    status_val = "ignored"
                elif meta.get("relevance") == "unapproved_request":
                    status_val = "excluded"
                else:
                    status_val = "applied"
                try:
                    apply_message_to_store(
                        message_meta=meta,
                        msg_facts=m_facts,
                        msg_constraints=m_cons,
                        seq=seq,
                        resolved_date=r_date,
                        candidate_facts=candidate_facts,
                        candidate_constraints=candidate_constraints,
                        policy=policy,
                        trace=trace,
                    )
                except ProtectedFactViolation as pv:
                    status_val = "rejected"
                    state.setdefault("rejections", []).append(
                        {
                            "seq": seq,
                            "sender": meta.get("sender", "Unknown"),
                            "text": b["text"],
                            "check": "protected",
                            "reason": str(pv),
                        }
                    )
                    trace.python_event(
                        "REJECT",
                        f"message {seq} ({meta.get('sender', 'Unknown')}): {pv}.",
                    )

                candidate_messages.append(
                    {
                        "seq": seq,
                        "hash": b["hash"],
                        "text": b["text"],
                        "resolved_date": r_date,
                        "meta": meta,
                        "status": status_val,
                    }
                )

            areas = affected_areas(set(), is_fresh=True)
            recomputed_union.update(areas)
            trace.python_event("ROUTER", f"affected areas: {', '.join(areas)}")

            candidate_plan = build_plan(
                facts=candidate_facts,
                constraints=candidate_constraints,
                previous_plan=None,
                areas=areas,
                policy=policy,
                trace=trace,
            )
            verdict = validate_plan(candidate_plan, candidate_facts, candidate_constraints)
            candidate_plan["valid"] = verdict["passed"]
            candidate_plan["checks"] = verdict["checks"]
            candidate_plan["warnings"].extend(verdict.get("unevaluated_warnings", []))
            for uw in verdict.get("unevaluated_warnings", []):
                trace.python_event("WARNING", uw)

            official_passed = sum(
                1
                for c in verdict["checks"]
                if c["id"] in {"figures", "budget", "venue_fit", "schedule", "judges", "coverage"}
                and c["passed"]
            )
            trace.python_event("VALIDATE", f"{official_passed}/6 checks passed")

            state["messages"] = candidate_messages
            state["facts"] = candidate_facts
            state["constraints"] = candidate_constraints
            state["plan"] = candidate_plan
            trace.python_event("COMMIT", f"plan v{candidate_plan['version']} saved")

        else:
            # Update mode: process each new message sequentially one at a time
            for b in new_blocks:
                bid = int(b["id"])
                seq = next_seq
                next_seq += 1
                meta = meta_by_id.get(
                    bid,
                    {
                        "id": bid,
                        "sender": "Unknown",
                        "channel": "other",
                        "date": None,
                        "relevance": "relevant",
                        "reason": "",
                    },
                )
                sender = str(meta.get("sender") or "Unknown")
                r_date = resolve_message_date(
                    meta.get("date"),
                    state["facts"],
                    state["messages"],
                    mode="update",
                    pack_year=pack_year,
                )
                m_facts = facts_by_id.get(bid, [])
                m_cons = constraints_by_id.get(bid, [])

                if meta.get("relevance") == "irrelevant":
                    trace.python_event(
                        "IGNORE",
                        f"IGNORED message {seq} ({sender}): {meta.get('reason', 'irrelevant')}",
                    )
                    state["messages"].append(
                        {
                            "seq": seq,
                            "hash": b["hash"],
                            "text": b["text"],
                            "resolved_date": r_date,
                            "meta": meta,
                            "status": "ignored",
                        }
                    )
                    continue

                cand_facts = copy.deepcopy(state["facts"])
                cand_cons = copy.deepcopy(state["constraints"])

                try:
                    changed = apply_message_to_store(
                        message_meta=meta,
                        msg_facts=m_facts,
                        msg_constraints=m_cons,
                        seq=seq,
                        resolved_date=r_date,
                        candidate_facts=cand_facts,
                        candidate_constraints=cand_cons,
                        policy=policy,
                        trace=trace,
                    )
                except ProtectedFactViolation as pv:
                    reason_str = str(pv)
                    state["rejections"].append(
                        {
                            "seq": seq,
                            "sender": sender,
                            "text": b["text"],
                            "check": "protected",
                            "reason": reason_str,
                        }
                    )
                    state["messages"].append(
                        {
                            "seq": seq,
                            "hash": b["hash"],
                            "text": b["text"],
                            "resolved_date": r_date,
                            "meta": meta,
                            "status": "rejected",
                        }
                    )
                    trace.python_event(
                        "REJECT",
                        f"message {seq} ({sender}): {reason_str}. Plan unchanged.",
                    )
                    continue

                if not changed:
                    state["messages"].append(
                        {
                            "seq": seq,
                            "hash": b["hash"],
                            "text": b["text"],
                            "resolved_date": r_date,
                            "meta": meta,
                            "status": "applied",
                        }
                    )
                    state["facts"] = cand_facts
                    state["constraints"] = cand_cons
                    continue

                areas = affected_areas(changed, is_fresh=False)
                trace.python_event("ROUTER", f"affected areas: {', '.join(areas)}")

                cand_plan = build_plan(
                    facts=cand_facts,
                    constraints=cand_cons,
                    previous_plan=state.get("plan"),
                    areas=areas,
                    policy=policy,
                    trace=trace,
                )
                verdict = validate_plan(cand_plan, cand_facts, cand_cons)

                if verdict["passed"]:
                    cand_plan["valid"] = True
                    cand_plan["checks"] = verdict["checks"]
                    cand_plan["warnings"].extend(verdict.get("unevaluated_warnings", []))
                    for uw in verdict.get("unevaluated_warnings", []):
                        trace.python_event("WARNING", uw)
                    state["facts"] = cand_facts
                    state["constraints"] = cand_cons
                    state["plan"] = cand_plan
                    state["messages"].append(
                        {
                            "seq": seq,
                            "hash": b["hash"],
                            "text": b["text"],
                            "resolved_date": r_date,
                            "meta": meta,
                            "status": "applied",
                        }
                    )
                    recomputed_union.update(areas)
                    trace.python_event("VALIDATE", "6/6 checks passed")
                    trace.python_event("COMMIT", f"plan v{cand_plan['version']} saved")
                else:
                    first_fail = (
                        verdict["failures"][0]
                        if verdict["failures"]
                        else {"check": "validation", "reason": "Rejected: validation failed"}
                    )
                    chk_id = first_fail["check"]
                    reason_str = first_fail["reason"]
                    clean_reason = reason_str.replace("Rejected: ", "")
                    state["rejections"].append(
                        {
                            "seq": seq,
                            "sender": sender,
                            "text": b["text"],
                            "check": chk_id,
                            "reason": reason_str,
                        }
                    )
                    state["messages"].append(
                        {
                            "seq": seq,
                            "hash": b["hash"],
                            "text": b["text"],
                            "resolved_date": r_date,
                            "meta": meta,
                            "status": "rejected",
                        }
                    )
                    trace.python_event(
                        "REJECT",
                        f"message {seq} ({sender}): {clean_reason}. Plan unchanged.",
                    )

        # Finalize state and outputs
        _refresh_message_statuses(
            state.get("messages") or [],
            state.get("facts") or [],
            state.get("constraints") or [],
        )
        elapsed_seconds = round(time.monotonic() - t_start, 2)
        state["runs"] = run_number
        state["last_run_seconds"] = elapsed_seconds
        state["session_tokens"] = int(state.get("session_tokens", 0)) + trace.total_tokens

        final_plan = state.get("plan") or {}
        final_plan["rejections"] = state.get("rejections", [])
        final_plan["recomputed_areas"] = [a for a in PLANNING_ORDER if a in recomputed_union]
        final_plan["timing"] = {"last_run_seconds": elapsed_seconds}
        final_plan["tokens"] = {
            "last_run": trace.total_tokens,
            "session": state["session_tokens"],
        }
        state["plan"] = final_plan

        run_trace_text = trace.format_run_trace()
        tr_dict = trace.to_dict()
        tr_dict["seconds"] = elapsed_seconds
        tr_dict["formatted"] = run_trace_text
        state.setdefault("trace_history", []).append(tr_dict)

        save_state(state, state_path)
        terminal_text = write_outputs(
            plan=final_plan,
            state=state,
            run_trace_text=run_trace_text,
            last_mode=mode,
        )
        print(terminal_text)
        return 0

    except Exception as exc:
        print(f"PYTHON | ERROR     | Unexpected error: {exc}. Previous valid plan preserved.")
        return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run.py <messages_file>")
        sys.exit(0)
    filepath = sys.argv[1]
    code = run_pipeline(filepath)
    sys.exit(code)


if __name__ == "__main__":
    main()
