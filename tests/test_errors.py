"""What happens when the person running this makes an ordinary mistake.

Running the CLI from the wrong directory is the single most likely thing a
reader of this repository will do, and a thirty-line traceback is a poor answer
to it. Each of these failures has to name the problem and the fix, and exit 2 —
distinct from exit 1, which this pipeline uses to mean "a gate failed", a result
rather than a mistake.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dante.errors import DanteError, MissingRegistry, MissingSources, NoRunYet
from dante.ingest import EXPECTED_FILES, load_sources
from dante.pipeline import load_registry

ROOT = Path(__file__).resolve().parents[1]


def test_missing_registry_says_where_to_run_from(tmp_path):
    with pytest.raises(MissingRegistry) as err:
        load_registry(tmp_path / "rules.yaml")
    assert "repository root" in err.value.fix


def test_missing_sources_names_them_all_at_once(tmp_path):
    (tmp_path / EXPECTED_FILES[0]).write_text("x")
    with pytest.raises(MissingSources) as err:
        load_sources(tmp_path)
    assert "11 of the source files" in err.value.problem
    assert "dante forge" in err.value.fix


def test_every_error_carries_a_fix():
    for exc in (MissingRegistry(Path("x")), NoRunYet(Path("y")),
                MissingSources(Path("z"), ["a.csv"])):
        assert isinstance(exc, DanteError)
        assert exc.problem and exc.fix
        assert exc.fix[0].islower(), "the fix reads as an instruction, not a sentence"


def _cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "dante.cli", *args],
                          capture_output=True, text=True, cwd=cwd,
                          env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src")})


def test_cli_from_the_wrong_directory_explains_itself(tmp_path):
    out = _cli("run", cwd=tmp_path)
    assert out.returncode == 2, out.stdout + out.stderr
    combined = out.stdout + out.stderr
    assert "rule registry" in combined
    assert "repository root" in combined
    assert "Traceback" not in combined


def test_cli_report_before_run_explains_itself(tmp_path):
    out = _cli("report", cwd=tmp_path)
    assert out.returncode == 2
    assert "dante run` first" in out.stdout + out.stderr
    assert "Traceback" not in out.stdout + out.stderr


def test_a_failing_gate_is_exit_one_not_exit_two(run):
    """The two codes mean different things and must not collapse into each other."""
    assert run["summary"]["verdict"] == "NO-GO"
    assert any(not g["passed"] for g in run["summary"]["gates"])
