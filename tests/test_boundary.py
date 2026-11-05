"""The engine may not see the answer key.

This is the claim the whole measurement rests on: the forge records every
defect it plants, and the pipeline that has to find them again never reads that
record. Stated in the README and in three docstrings, and until now enforced by
nothing at all — which is the kind of boundary that holds right up until
somebody adds one convenient import.

So it is checked here, structurally: no module the descent can reach may read
the ground-truth file, import the module that scores against it, or call the
generator that knows what the clean data looked like.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "dante"

# Everything `descend()` can reach. The forge, the scorer and the report are
# deliberately outside it: none of them makes a migration decision.
PIPELINE = [
    "run.py", "pipeline.py", "ingest.py", "assemble.py", "normalise.py",
    "triage.py", "finding.py", "errors.py",
] + sorted(f"circles/{p.name}" for p in (ENGINE / "circles").glob("c*.py"))

FORBIDDEN_CALLS = {"build_world", "forge", "recall", "planted_addresses"}
FORBIDDEN_MODULES = {"measure", "forge", "world"}


def _tree(rel: str) -> ast.Module:
    return ast.parse((ENGINE / rel).read_text())


def test_the_pipeline_covers_every_circle():
    """If a circle is missing from this list the whole check is theatre."""
    circles = {p.name for p in (ENGINE / "circles").glob("c*.py")}
    assert len(circles) == 9
    assert {f"circles/{c}" for c in circles} <= set(PIPELINE)


@pytest.mark.parametrize("rel", PIPELINE)
def test_no_pipeline_module_reads_the_ground_truth(rel):
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if "planted-defects" in value or "data/truth" in value:
                pytest.fail(f"{rel} names the ground-truth file")


@pytest.mark.parametrize("rel", PIPELINE)
def test_no_pipeline_module_imports_the_scorer_or_the_generator(rel):
    tree = _tree(rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            tail = node.module.rsplit(".", 1)[-1]
            if tail in FORBIDDEN_MODULES:
                imported = {a.name for a in node.names}
                # run.py takes two display strings off world; it may not take data
                allowed = {"CLIENT", "LEGACY_SYSTEM"} if tail == "world" else set()
                illegal = imported - allowed
                assert not illegal, f"{rel} imports {illegal} from {node.module}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                tail = alias.name.rsplit(".", 1)[-1]
                assert tail not in FORBIDDEN_MODULES, f"{rel} imports {alias.name}"


@pytest.mark.parametrize("rel", PIPELINE)
def test_no_pipeline_module_rebuilds_the_clean_world(rel):
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in FORBIDDEN_CALLS:
                pytest.fail(f"{rel} calls {name}()")


def test_the_scorer_is_not_reachable_from_the_descent():
    """A transitive import is still an import."""
    seen: set[str] = set()
    stack = ["run.py"]
    while stack:
        rel = stack.pop()
        if rel in seen or not (ENGINE / rel).exists():
            continue
        seen.add(rel)
        for node in ast.walk(_tree(rel)):
            if isinstance(node, ast.ImportFrom) and node.level and node.module:
                parts = node.module.split(".")
                candidate = ("/".join(parts)) + ".py"
                stack.append(candidate)
    assert "measure.py" not in seen, f"measure is reachable from the descent via {seen}"
