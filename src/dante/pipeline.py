"""The descent.

The nine circles are not decoration: they are the dependency order. You cannot
match duplicates before the names are normalised, cannot reconcile before the
money is parsed, and cannot check a foreign key before you know which records
survived. So the engine runs I to IX, and every circle may rely on everything
above it and nothing below it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .errors import MissingRegistry
from .finding import Finding

ENTITIES = ["customer", "supplier", "article", "open_item", "discount"]


@dataclass
class Context:
    raw_dir: Path
    rules: dict[str, dict[str, Any]]
    circles: dict[int, dict[str, Any]]
    sources: dict[str, pd.DataFrame] = field(default_factory=dict)
    norm: dict[str, pd.DataFrame] = field(default_factory=dict)
    candidates: dict[str, pd.DataFrame] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    merges: list[dict[str, Any]] = field(default_factory=list)

    def rule(self, rid: str) -> dict[str, Any]:
        if rid not in self.rules:
            raise KeyError(f"rule {rid} is not in the registry")
        return self.rules[rid]

    def finding(self, rid: str, entity: str, key: str, fieldname: str, source: str,
                raw: Any = None, repaired: Any = None, message: str = "",
                **evidence: Any) -> Finding:
        r = self.rule(rid)
        f = Finding(
            rule=rid, circle=r["circle"], entity=entity, key=str(key), field=fieldname,
            source=source, action=r["action"], owner=r["owner"], raw=raw,
            repaired=repaired, message=message or r["title"], evidence=evidence,
        )
        self.findings.append(f)
        return f


def load_registry(path: Path = Path("rules/rules.yaml")) -> tuple[dict, dict]:
    if not path.exists():
        raise MissingRegistry(path)
    doc = yaml.safe_load(path.read_text())
    rules = {r["id"]: r for r in doc["rules"]}
    circles = {c["number"]: c for c in doc["circles"]}
    return rules, circles
