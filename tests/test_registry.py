"""The registry is the contract: every rule is real, owned, and exercised."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

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


def test_quarantined_findings_are_owned_by_a_human():
    for rule_id, owner in [(r["id"], r["owner"]) for r in RULES
                           if r["action"] == "quarantine"]:
        assert owner != "engine", f"{rule_id} asks a human and names the engine"


def test_rules_only_fire_on_entities_they_declare(run):
    """The entity list is a claim about reach, so the run has to back it up.

    R-I-02 declared customers, suppliers and articles while circle I normalises
    every source table, receivables included — so it was firing on an entity it
    had not claimed. The opposite case is allowed: a rule may cover an entity
    this particular dataset happens not to damage.
    """
    import collections

    import pandas as pd
    findings = pd.read_csv(run["out"] / "report" / "findings.csv")
    fired = collections.defaultdict(set)
    for rule_id, entity in zip(findings["rule"], findings["entity"], strict=False):
        fired[rule_id].add(entity)

    declared = {r["id"]: set(r["entity"]) for r in RULES}
    undeclared = {
        rule_id: sorted(entities - declared[rule_id])
        for rule_id, entities in fired.items()
        if entities - declared[rule_id]
    }
    assert not undeclared, f"rules firing on an entity they do not declare: {undeclared}"


def test_every_declared_entity_is_a_real_one(run):
    known = set(run["summary"]["counts"]) | {"all"}
    for r in RULES:
        unknown = set(r["entity"]) - known
        assert not unknown, f"{r['id']} declares {unknown}, which is not an entity"


def test_the_registry_does_not_contradict_the_code():
    """A rationale that names the wrong scorer is worse than none at all.

    R-II-01 said token_set_ratio while circle II uses token_sort_ratio — the one
    distinction the README makes a point of — and R-II-02 quoted a grey band of
    80 after the constant moved to 75. Both read as authoritative and both were
    wrong, which is the expensive kind of documentation.
    """
    from dante.circles import c2_lust

    text = (ROOT / "rules/rules.yaml").read_text()
    rules = {r["id"]: " ".join(r["rationale"].split()) for r in RULES}

    assert "token_sort_ratio" in rules["R-II-01"]
    assert "scored with token_set_ratio" not in rules["R-II-01"], \
        "the registry names the scorer this engine deliberately does not use"

    assert str(c2_lust.AUTO_MERGE) in rules["R-II-01"], \
        f"R-II-01 should quote the auto-merge threshold ({c2_lust.AUTO_MERGE})"
    assert str(c2_lust.GREY_BAND) in rules["R-II-02"], \
        f"R-II-02 should quote the grey band floor ({c2_lust.GREY_BAND})"
    assert str(c2_lust.AUTO_MERGE) in rules["R-II-02"]
    assert text.count("token_set_ratio") <= 1, \
        "the rejected scorer should appear only where it is being rejected"


def test_the_registry_does_its_own_arithmetic_correctly():
    """R-VII-03 claimed 45291 was 2023-12-27. It is 2023-12-31."""
    import re

    from dante.normalise import parse_date

    for rule in RULES:
        text = " ".join(rule["rationale"].split())
        for serial, claimed in re.findall(r"\b(\d{5}) is (\d{4}-\d{2}-\d{2})\b", text):
            value, status = parse_date(serial)
            assert status == "serial", f"{rule['id']}: {serial} is not read as a serial"
            assert value.isoformat() == claimed, \
                f"{rule['id']} says {serial} is {claimed}; it is {value.isoformat()}"
