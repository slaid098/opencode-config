"""Tests for .opencode/scripts/check-adr-refs.py — dangling ADR reference guard.

Covers the deterministic ADR-ref guard: clean repo passes, a dangling
``ADR-999`` in a temp handoff is detected, self-reference inside an
``NNN-*.md`` file is excluded, a valid cross-ref (``ADR-002``) passes,
a file with no ADR refs passes, and ``node_modules/`` is excluded.

Strategy mirrors ``tests/test_check_permissions.py``:
- ``test_clean_repo_passes`` runs the script as a subprocess on the
  real (clean) repo — black-box, returncode 0, OK message in stdout.
- The remaining tests load the script in-process via importlib and
  monkeypatch ``REPO_ROOT`` / ``ADR_DIR`` to point at a tmp_path tree,
  then call ``main()`` and assert on captured stdout / SystemExit code.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / ".opencode" / "scripts" / "check-adr-refs.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_adr_refs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_adr_refs"] = module
    spec.loader.exec_module(module)
    return module


car = _load_script()


# ── clean repo (subprocess black-box) ───────────────────────────────────────


def test_clean_repo_passes():
    """On the current (clean) repo the script exits 0 with the OK message."""
    result = subprocess.run(
        ["python3", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK: No dangling ADR references." in result.stdout


# ── helpers for in-process tests ────────────────────────────────────────────


def _setup_tmp_repo(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """Point the script's REPO_ROOT and ADR_DIR at a tmp_path tree.

    Creates the ``docs/decisions/`` dir and returns (repo_root, adr_dir).
    """
    repo = tmp_path / "repo"
    adr_dir = repo / "docs" / "decisions"
    adr_dir.mkdir(parents=True)
    handoff_dir = repo / "docs" / "handoff"
    handoff_dir.mkdir(parents=True)
    monkeypatch.setattr(car, "REPO_ROOT", repo)
    monkeypatch.setattr(car, "ADR_DIR", adr_dir)
    return repo, adr_dir


# ── dangling reference detected ─────────────────────────────────────────────


def test_dangling_ref_detected(tmp_path, monkeypatch, capsys):
    """A handoff referencing ADR-999 (no 999-*.md) → exit 1 + ADR-999 in output."""
    repo, _adr_dir = _setup_tmp_repo(tmp_path, monkeypatch)
    (repo / "docs" / "handoff" / "pr-1-test.md").write_text("See ADR-999 for context.\n")

    with pytest.raises(SystemExit) as exc_info:
        car.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ADR-999" in captured.out
    assert "FAIL" in captured.out


# ── self-reference excluded ─────────────────────────────────────────────────


def test_self_reference_excluded(tmp_path, monkeypatch, capsys):
    """An ADR file ``019-pr-94-test.md`` mentioning ADR-019 → passes (self-ref)."""
    _repo, adr_dir = _setup_tmp_repo(tmp_path, monkeypatch)
    (adr_dir / "019-pr-94-test.md").write_text("# ADR-019: self-reference is OK.\n")

    with pytest.raises(SystemExit) as exc_info:
        car.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "OK: No dangling ADR references." in captured.out


# ── valid cross-reference passes ────────────────────────────────────────────


def test_valid_cross_ref_passes(tmp_path, monkeypatch, capsys):
    """A handoff referencing ADR-002 when 002-*.md exists → passes."""
    repo, adr_dir = _setup_tmp_repo(tmp_path, monkeypatch)
    (adr_dir / "002-pr-56-pipeline-mandatory-adr.md").write_text("# ADR-002\n")
    (repo / "docs" / "handoff" / "pr-3-test.md").write_text("Per ADR-002, ADR is mandatory.\n")

    with pytest.raises(SystemExit) as exc_info:
        car.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "OK: No dangling ADR references." in captured.out


# ── no ADR refs in a file passes ────────────────────────────────────────────


def test_no_adr_refs_passes(tmp_path, monkeypatch, capsys):
    """A handoff with no ADR-NNN references → passes."""
    repo, _adr_dir = _setup_tmp_repo(tmp_path, monkeypatch)
    (repo / "docs" / "handoff" / "pr-4-test.md").write_text("No ADR references here.\n")

    with pytest.raises(SystemExit) as exc_info:
        car.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "OK: No dangling ADR references." in captured.out


# ── node_modules excluded ───────────────────────────────────────────────────


def test_exclude_node_modules(tmp_path, monkeypatch, capsys):
    """A ``.md`` file under ``node_modules/`` with ADR-999 is NOT scanned."""
    repo, _adr_dir = _setup_tmp_repo(tmp_path, monkeypatch)
    nm = repo / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / "README.md").write_text("Dangling ADR-999 should be ignored.\n")

    with pytest.raises(SystemExit) as exc_info:
        car.main()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "OK: No dangling ADR references." in captured.out
    assert "ADR-999" not in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
