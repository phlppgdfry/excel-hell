"""A finding is one rule meeting one cell. Everything downstream is a view on these."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# What a human answer does to the finding it answers. A ruling is a correction
# the owner made once for every record that asked the same question, so it has
# the same effect as one. `reject` is deliberately not reachable in the other
# direction: see decisions.py.
EFFECT = {"accept": "repair", "correct": "repair", "reject": "reject",
          "ruling": "repair"}


@dataclass
class Finding:
    rule: str
    circle: int
    entity: str
    key: str
    field: str
    source: str
    action: str           # repair | quarantine | reject
    owner: str
    raw: Any = None
    repaired: Any = None
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    decision: str | None = None     # accept | correct | reject, once answered
    decided_by: str | None = None

    @property
    def effective_action(self) -> str:
        """What this finding means for the row now, answer included.

        Triage reads this and never `action`, so a question that has been
        answered stops holding a row back. The original action stays on the
        record, because the audit trail has to show that the engine held the
        row and a named person released it.
        """
        return EFFECT[self.decision] if self.decision else self.action

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["raw"] = _s(self.raw)
        d["repaired"] = _s(self.repaired)
        d["effective_action"] = self.effective_action
        return d


def _s(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= 160 else s[:157] + "..."


ACTION_RANK = {"repair": 0, "quarantine": 1, "reject": 2, "gate": 3}
