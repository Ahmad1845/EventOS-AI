"""Comprehensive pytest suite for EventOS per Section 22."""

import copy
import json
import os
import subprocess

from core.extractor import Extractor, normalize_value, strip_and_find_json
from core.factstore import (
    ProtectedFactViolation,
    apply_message_to_store,
    get_winning_facts,
    resolve_message_date,
)
from core.ingest import ingest_file
from core.llm import LLMResult
from core.planner import build_plan
from core.router import PLANNING_ORDER, affected_areas, model_call_areas
from core.trace import Trace
from core.validator import validate_plan


DEFAULT_POLICY = {
    "judges_engaged": "minimum_required",
    "opening_minutes": 15,
    "closing_minutes": 15,
    "build_split_before_breaks": 0.5,
    "protect_approved_facts": True,
    "exclude_unapproved_requests": True,
    "food_preference": "default_then_cheapest",
    "sender_match_threshold": 0.6,
}


def load_fixture():
    path = os.path.join("tests", "fixtures", "synthetic_facts.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_ingest_splitting():
    blocks = ingest_file(os.path.join("tests", "packs", "sample_pack.txt"))
    assert len(blocks) == 8
    assert blocks[0]["id"] == 1
    assert blocks[7]["id"] == 8
    assert len(blocks[0]["hash"]) == 40

    single = ingest_file(os.path.join("tests", "packs", "practice_change.txt"))
    assert len(single) == 1


def test_solvers_and_planner_on_fixture():
    data = load_fixture()
    facts = data["facts"]
    constraints = data["constraints"]

    # 90 students / 3 = 30 teams; 30 / 3 = 10 required judges; headcount = 90 + 6 + 10 = 106
    plan = build_plan(facts, constraints, None, PLANNING_ORDER, DEFAULT_POLICY)
    assert plan["headcount"]["total"] == 106
    assert plan["judging"]["teams"] == 30
    assert plan["judging"]["required"] == 10
    assert plan["judging"]["engaged"] == 10
    assert plan["judging"]["window_minutes"] == 30
    assert plan["judging"]["honorarium_total"] == 40000

    # Cheapest fitting venue for 106 is room_beta (120 seats at 90000)
    assert plan["venue"]["slug"] == "room_beta"
    assert plan["venue"]["price"] == 90000

    # Require feature backup_power -> filters out room_beta, picks room_gamma
    cons_feat = constraints + [
        {
            "msg": 2,
            "area": "venue",
            "type": "require_feature",
            "target": "backup_power",
            "op": None,
            "value": "backup_power",
            "unit": None,
            "hard": True,
            "text": "Need backup power",
        }
    ]
    plan_feat = build_plan(facts, cons_feat, None, PLANNING_ORDER, DEFAULT_POLICY)
    assert plan_feat["venue"]["slug"] == "room_gamma"

    # Schedule sums to duration (180)
    assert plan["schedule"]["duration_minutes"] == 180
    assert sum(b["minutes"] for b in plan["schedule"]["blocks"]) == 180

    # Budget downgrade test: lower cap so standard_meal (95400) exceeds cap, downgrades to lite_meal (53000)
    tight_facts = copy.deepcopy(facts)
    for tf in tight_facts:
        if tf["key"] == "budget.cap":
            tf["value"] = 250000
    plan_downgraded = build_plan(tight_facts, constraints, None, PLANNING_ORDER, DEFAULT_POLICY)
    assert plan_downgraded["food"]["slug"] == "lite_meal"
    assert plan_downgraded["budget"]["total"] <= 250000


def test_validator_eight_checks():
    data = load_fixture()
    facts = data["facts"]
    constraints = data["constraints"]
    plan = build_plan(facts, constraints, None, PLANNING_ORDER, DEFAULT_POLICY)

    verdict = validate_plan(plan, facts, constraints)
    assert verdict["passed"] is True

    # 1. Break figures
    bad_fig = copy.deepcopy(plan)
    bad_fig["food"]["cost"] = 123
    assert validate_plan(bad_fig, facts, constraints)["passed"] is False

    # 2. Break budget
    bad_bud = copy.deepcopy(plan)
    bad_bud["budget"]["total"] = 999999
    bad_bud["budget"]["items"][0]["amount"] = 999999
    v_bud = validate_plan(bad_bud, facts, constraints)
    assert v_bud["passed"] is False
    assert any(f["check"] == "budget" for f in v_bud["failures"])

    # 3 & 8. Break floors / food_quantity
    bad_food = copy.deepcopy(plan)
    bad_food["food"]["quantity"] = 50
    bad_food["food"]["cost"] = 50 * bad_food["food"]["unit_price"]
    v_food = validate_plan(bad_food, facts, constraints)
    assert v_food["passed"] is False
    assert any("below the 106 people to feed" in f["reason"] for f in v_food["failures"])


def test_factstore_conflict_fuzzy_and_protected():
    facts = []
    constraints = []
    trace = Trace(1, "fresh", "test.txt", 2)

    meta1 = {"id": 1, "sender": "Dean Office", "date": "2026-11-01", "relevance": "relevant"}
    f1 = [
        {"msg": 1, "key": "event.students", "value": 150, "unit": None, "kind": "approval"},
        {"msg": 1, "key": "food.option.standard_lunch_box.unit_price", "value": 1000, "unit": "PKR", "kind": "quote"},
    ]
    apply_message_to_store(meta1, f1, [], 1, "2026-11-01", facts, constraints, DEFAULT_POLICY, trace)

    # Fuzzy slug standard_lunch -> standard_lunch_box & newer date wins
    meta2 = {"id": 2, "sender": "Caterer", "date": "2026-11-12", "relevance": "relevant"}
    f2 = [
        {"msg": 2, "key": "food.option.standard_lunch.unit_price", "value": 1200, "unit": "PKR", "kind": "quote"},
    ]
    changed = apply_message_to_store(meta2, f2, [], 2, "2026-11-12", facts, constraints, DEFAULT_POLICY, trace)
    assert "food.option.standard_lunch_box.unit_price" in changed
    winning = get_winning_facts(facts)
    assert winning["food.option.standard_lunch_box.unit_price"] == 1200

    # Protected fact violation by unauthorized sender
    meta3 = {"id": 3, "sender": "Random Student", "date": "2026-11-15", "relevance": "relevant"}
    f3 = [{"msg": 3, "key": "event.students", "value": 50, "unit": None, "kind": "override"}]
    raised = False
    try:
        apply_message_to_store(meta3, f3, [], 3, "2026-11-15", facts, constraints, DEFAULT_POLICY, trace)
    except ProtectedFactViolation:
        raised = True
    assert raised is True


def test_router_dependency_table():
    assert affected_areas(["budget.committed.printing"]) == ["budget"]
    assert affected_areas(["food.option.standard.unit_price"]) == ["food", "budget"]
    assert affected_areas(["venue.option.hall_a.price"]) == ["venue", "budget"]
    assert affected_areas(["event.students"]) == ["judging", "venue", "food", "schedule", "budget"]
    assert affected_areas(["event.duration_minutes"]) == ["schedule"]
    assert affected_areas(["judging.rate"]) == ["judging", "budget"]
    assert model_call_areas() == ["reading"]


def test_extractor_repair_and_retry():
    class StubLLM:
        def __init__(self):
            self.calls = 0

        def call(self, system, user, tag="reading"):
            self.calls += 1
            if self.calls == 1:
                return LLMResult("stub-model", "not valid json {{{", 10, 5, 15, 0.1)
            valid_payload = {
                "messages": [{"id": 1, "sender": "Finance", "channel": "email", "date": "2026-11-10", "relevance": "relevant", "reason": "cost"}],
                "facts": [{"msg": 1, "key": "budget.committed.printing", "value": "Rs 15,000", "unit": "PKR", "kind": "commitment"}],
                "constraints": [],
            }
            return LLMResult("stub-model", "```json\n" + json.dumps(valid_payload) + "\n```", 12, 20, 32, 0.1)

    trace = Trace(1, "update", "stub.txt", 1)
    ext = Extractor(StubLLM(), trace)
    res = ext.run([{"id": 1, "text": "Printing Rs 15,000", "hash": "abc"}])
    assert len(trace.model_calls) == 2
    assert res["facts"][0]["value"] == 15000
    assert normalize_value("10k") == 10000
    assert normalize_value("1.5 lakh") == 150000
    assert normalize_value("fifteen") == 15


def test_code_audit_no_hardcoded_pack_facts():
    """Verify Section 22.9 audit: grep -nE '[0-9]{3,}' core/ run.py shows no pack values."""
    proc = subprocess.run(
        ["grep", "-rnE", "[0-9]{3,}", "core/", "run.py"],
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == "", f"Found 3+ digit numbers in code:\n{proc.stdout}"
