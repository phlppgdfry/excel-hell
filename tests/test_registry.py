"""The registry is the contract: every rule is real, owned, and exercised."""

from __future__ import annotations

import yaml

from tests.conftest import ROOT

REGISTRY = yaml.safe_load((ROOT / "rules/rules.yaml").read_text())
RULES = REGISTRY["rules"]
ACTIONS = {"repair", "quarantine", "reject", "gate"}
OWNERS = {"engine", "sales", "finance", "purchasing", "operations"}


def test_rule_ids_are_unique():
    ids = [r["id"] for r in RULES]
    assert len(ids) == len(set(ids))


def test_nine_circles_each_with_rules():
    circles = {c["number"] for c in REGISTRY["circles"]}
    assert circles == set(range(1, 10))
    for n in circles:
        assert [r for r in RULES if r["circle"] == n], f"circle {n} has no rules"


def test_every_rule_declares_an_action_an_owner_and_a_reason():
    for r in RULES:
        assert r["action"] in ACTIONS, r["id"]
        assert r["owner"] in OWNERS, r["id"]
        assert len(r["rationale"].split()) >= 12, f"{r['id']} needs a real rationale"
        assert r["entity"], r["id"]


def test_rule_id_matches_its_circle():
    roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
             8: "VIII", 9: "IX"}
    for r in RULES:
        assert r["id"].startswith(f"R-{roman[r['circle']]}-"), r["id"]


def test_every_rule_fires_at_least_once(run):
    """A rule nobody triggers is documentation, not a control."""
    fired = set(run["summary"]["findings_by_rule"])
    missing = [r["id"] for r in RULES if r["action"] != "gate" and r["id"] not in fired]
    assert not missing, f"rules that never fired: {missing}"


def test_every_gate_is_evaluated(run):
    gates = {g["rule"] for g in run["summary"]["gates"]}
    assert gates == {r["id"] for r in RULES if r["action"] == "gate"}


def test_quarantined_findings_are_owned_by_a_human(run):
    for rule_id, owner in [(r["id"], r["owner"]) for r in RULES
                           if r["action"] == "quarantine"]:
        assert owner != "engine", f"{rule_id} asks a human and names the engine"
