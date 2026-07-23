"""Tests for .opencode/scripts/pipeline-status.py — mandatory ADR by PR#.

Verifies the deterministic check_adr: ADR is required for every PR and is
found by ``*-pr-<N>-*.md`` filename pattern (no regex guessing in handoff).
"""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / ".opencode" / "scripts" / "pipeline-status.py"
)
spec = importlib.util.spec_from_file_location("pipeline_status", SCRIPT_PATH)
ps = importlib.util.module_from_spec(spec)
sys.modules["pipeline_status"] = ps
spec.loader.exec_module(ps)


def test_adr_exists_for_pr(tmp_path, monkeypatch):
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-55-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)

    result = ps.check_adr(55)

    assert result.status == ps.PhaseStatus.DONE
    assert "002-pr-55-test.md" in result.detail


def test_adr_missing_for_pr(tmp_path, monkeypatch):
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)

    result = ps.check_adr(55)

    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не найден" in result.detail
    assert "scaffold-handoff.sh 55" in result.detail


def test_old_pr_without_pr_in_filename(tmp_path, monkeypatch):
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "001-data-bus-pipeline.md").write_text("# ADR-001")
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)

    result = ps.check_adr(46)

    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не найден" in result.detail
