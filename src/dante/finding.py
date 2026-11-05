"""A finding is one rule meeting one cell. Everything downstream is a view on these."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["raw"] = _s(self.raw)
        d["repaired"] = _s(self.repaired)
        return d


def _s(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= 160 else s[:157] + "..."


ACTION_RANK = {"repair": 0, "quarantine": 1, "reject": 2, "gate": 3}
