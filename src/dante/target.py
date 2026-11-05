"""What "load-ready" means, stated as the target's own field names.

A clean CSV with a column called `vat` is not load-ready for anything. It is
load-ready for Business Central when it is called `VAT Registration No.`, sits
in a file shaped like the Customer table, and the fields that need a setup
record before they will insert are named out loud rather than discovered by the
consultant at eleven at night.

So the mapping is data, like the rules, and it carries three kinds of entry:
a field that maps, a field that maps and needs a setup record first, and a
column that is not migrated with the reason written down. The third kind is
the one a reviewer should read first, because every migration has them and
most mappings pretend otherwise.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .errors import DanteError

DEFAULT_MAPPING = Path("mapping/business-central.yaml")


class MissingMapping(DanteError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"there is no target mapping at {path}",
            "run this from the repository root, or pass --mapping <path to a "
            "mapping yaml>",
        )


class NothingToLoad(DanteError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"there is no load-ready data in {path}",
            "run `dante run` first — it writes out/paradiso/<entity>.csv, which "
            "is what this shapes for the target",
        )


def load_mapping(path: Path = DEFAULT_MAPPING) -> dict[str, Any]:
    if not path.exists():
        raise MissingMapping(path)
    return yaml.safe_load(path.read_text())


def slug(table: str) -> str:
    return table.lower().replace(".", "").replace(" ", "-")


def shape(df: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """One load file: the target's columns, in the target's order."""
    out = pd.DataFrame(index=df.index)
    for column, value in (spec.get("constants") or {}).items():
        out[column] = value
    for f in spec["fields"]:
        out[f["to"]] = _column(df, f)
    return out


def _column(df: pd.DataFrame, f: dict[str, Any]) -> pd.Series:
    sources = f["from"] if isinstance(f["from"], list) else [f["from"]]
    present = [s for s in sources if s in df.columns]
    if not present:
        return pd.Series([""] * len(df), index=df.index)

    parts = [df[s].map(_text) for s in present]
    series = parts[0]
    for extra in parts[1:]:
        # join, not concatenate: a customer with no box number should not
        # arrive with a trailing space in its address
        series = (series + f.get("join", " ") + extra).map(str.strip)
    series = series.map(lambda v: " ".join(v.split()))

    if "values" in f:
        table = {k.upper(): v for k, v in f["values"].items()}
        series = series.map(lambda v: table.get(v.upper(), f.get("default", v)))
    return series


def _text(v: Any) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return ""
    s = str(v)
    return "" if s in ("nan", "None") else s


def build(paradiso: Path, out: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    """Shape every load-ready entity into its target table."""
    files = {e: paradiso / f"{e}.csv" for e in mapping["entities"]}
    if not any(p.exists() for p in files.values()):
        raise NothingToLoad(paradiso)

    out.mkdir(parents=True, exist_ok=True)
    tables: list[dict[str, Any]] = []
    for entity in mapping["target"]["order"]:
        spec = mapping["entities"][entity]
        source = files[entity]
        if not source.exists():
            continue
        df = pd.read_csv(source, dtype=str, keep_default_na=False)
        shaped = shape(df, spec)
        path = out / f"{slug(spec['table'])}.csv"
        shaped.to_csv(path, index=False)
        tables.append({
            "entity": entity,
            "table": spec["table"],
            "table_no": spec["table_no"],
            "rows": len(shaped),
            "columns": list(shaped.columns),
            "file": str(path),
            "needs": [{"field": f["to"], "why": " ".join(f["needs"].split()),
                       "codes": [str(c) for c in f.get("setup_codes", [])]}
                      for f in spec["fields"] if f.get("needs")],
            "dropped": [{"column": d["column"], "why": " ".join(d["why"].split())}
                        for d in (spec.get("drop") or [])],
        })
    return {"target": mapping["target"], "tables": tables,
            "rows": sum(t["rows"] for t in tables),
            "blocking": sum(len(t["needs"]) for t in tables)}
