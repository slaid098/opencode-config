"""Tests for config/tools/spec-status.ts — the spec_status custom tool.

Mirrors ``tests/test_pipeline_status_tool.py``: exercises the tool's
``execute()`` function via ``tests/_ts_loader.mjs`` (a node CommonJS
sandbox that strips TS-only syntax, stubs ``@opencode-ai/plugin``, and
replaces ``import.meta.dir`` with the real ``config/tools`` directory).

The loader is parameterized via the ``TS_FILE`` env var (PR#109) so the
same harness works for both ``pipeline-status.ts`` and ``spec-status.ts``
without breaking existing callers (``TS_FILE`` unset → defaults to
``pipeline-status.ts``). These tests set ``TS_FILE=config/tools/spec-status.ts``.

Modes used (same as pipeline-status tool tests):
- ``load`` — sanity-check that the tool loads and has the expected args.
- ``exec_stub`` — call execute with a stubbed spawnSync to verify:
  (a) args passed correctly (``--validate`` flag when ``validate: true``),
  (b) stdout is trimmed on success,
  (c) non-zero exit returns an actionable error message,
  (d) ``cwd`` is propagated from ``context.worktree`` (ADR-023).
- ``exec_real`` — call execute against the real spec-status.py
  (integration test, skipped if no gh auth — though spec-status.py itself
  does not require gh auth for Phases 0-7; only Phase 8 hits gh).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = REPO_ROOT / "tests" / "_ts_loader.mjs"
TS_FILE = REPO_ROOT / "config" / "tools" / "spec-status.ts"
TS_FILE_REL = "config/tools/spec-status.ts"


def _gh_available() -> bool:
    """True if `gh auth status` succeeds (local dev machine, not CI runner)."""
    try:
        return (
            subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except FileNotFoundError:
        return False


_GH_OK = _gh_available()
_SKIP_REASON = "gh CLI not authenticated — skip real spec-status.py call"


def _run_loader(*args: str, stdin: str | None = None) -> dict:
    """Invoke the loader with ``TS_FILE`` env set to spec-status.ts and parse JSON stdout."""
    env = {**os.environ, "TS_FILE": TS_FILE_REL}
    proc = subprocess.run(
        ["node", str(LOADER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
        input=stdin,
        timeout=60,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"_ts_loader.mjs {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return json.loads(proc.stdout)


def test_loader_can_load_tool():
    """Sanity: spec-status.ts loads and has the ``validate`` arg (optional)."""
    if not TS_FILE.exists():
        pytest.skip("spec-status.ts not present")
    out = _run_loader("load")
    assert "description" in out
    # spec-status.ts declares: validate (optional boolean)
    assert "validate" in out["args"]


def test_execute_no_validate_flag():
    """execute() without ``validate: true`` calls spawnSync WITHOUT ``--validate``.

    Default path: ``args.validate`` is undefined/falsy → ``cmdArgs = []`` →
    spawnSync argv is ``[script]`` (no ``--validate``).
    """
    # exec_stub args: <validate_str> <stub_status> <stub_stdout> <stub_stderr>
    # validate_str="false" → parseInt(false)=NaN → falsy → no --validate
    out = _run_loader("exec_stub", "false", "0", "spec output", "")
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    call = calls[0]
    assert call["cmd"] == "python3"
    assert call["args"][0] == str(REPO_ROOT / "config" / "scripts" / "spec-status.py"), (
        f"script path mismatch: {call['args'][0]}"
    )
    # No --validate in args (only the script path is present).
    assert "--validate" not in call["args"], f"unexpected --validate in args: {call['args']}"


def test_execute_passes_validate_flag():
    """execute() with ``validate: true`` adds ``--validate`` to spawnSync argv."""
    # validate_str="true" → Boolean(true) → cmdArgs = ["--validate"]
    out = _run_loader("exec_stub", "true", "0", "spec validate output", "")
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    call = calls[0]
    assert "--validate" in call["args"], f"expected --validate in args: {call['args']}"


def test_execute_trims_stdout():
    """execute trims leading/trailing whitespace from the script stdout."""
    raw_stdout = "  trimmed-spec-output  \n"
    out = _run_loader("exec_stub", "false", "0", raw_stdout, "")
    result = out["result"]
    assert result == "trimmed-spec-output", f"expected trimmed output, got: {result!r}"


def test_execute_nonzero_exit_returns_error():
    """execute returns an actionable error message on non-zero exit code."""
    out = _run_loader("exec_stub", "false", "1", "", "some stderr from spec-status")
    result = out["result"]
    assert "spec_status failed" in result
    assert "exit 1" in result
    assert "some stderr from spec-status" in result


def test_execute_uses_cwd_from_context():
    """execute passes ``cwd=context.worktree`` to spawnSync (ADR-023).

    The TS tool wrapper must propagate ``context.worktree`` as ``cwd`` to
    ``spawnSync`` so the Python script runs in the git worktree root
    (where ``docs/spec/`` lives), not in the opencode process cwd.
    """
    out = _run_loader("exec_stub", "false", "0", "spec ok", "")
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    opts = calls[0]["opts"]
    assert opts is not None, "spawnSync called without opts — expected cwd kwarg"
    assert "cwd" in opts, f"opts missing 'cwd' key — got: {opts}"
    assert opts["cwd"] == str(REPO_ROOT), (
        f"cwd must equal context.worktree ({REPO_ROOT}), got: {opts['cwd']!r}"
    )


@pytest.mark.skipif(not _GH_OK, reason=_SKIP_REASON)
def test_execute_real_spec_status():
    """Integration: execute() returns the real spec-status.py output.

    spec-status.py reads ``docs/spec/`` from cwd (REPO_ROOT). In this repo
    there is no ``docs/spec/``, so all 9 phases will be ❌ — that's a
    valid output (exit 0) and confirms the script ran through the loader.
    """
    if not (REPO_ROOT / "config" / "scripts" / "spec-status.py").exists():
        pytest.skip("spec-status.py not present")
    out = _run_loader("exec_real", "false")
    if out.get("error"):
        pytest.fail(f"execute raised: {out['error']}")
    result = out["result"]
    # spec-status.py output starts with "Spec: <project>" line.
    assert "Spec:" in result, f"expected 'Spec:' in output, got: {result[:200]!r}"
    # All 9 phases are present in the output (✅ or ❌ icons).
    assert "✅" in result or "❌" in result, (
        f"expected phase markers in output, got: {result[:200]!r}"
    )
