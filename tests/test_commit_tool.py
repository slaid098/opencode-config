"""Tests for .opencode/tools/commit.ts — the commit custom tool.

Mirrors tests/test_pipeline_status_tool.py / test_memory_setup_tool.py:
exercises the tool's ``execute()`` function via ``tests/_ts_loader.mjs``
using the ``exec_stub_json`` mode (multi-arg tools).

The loader is parameterized via the ``TS_FILE`` env var. These tests set
``TS_FILE=.opencode/tools/commit.ts``.

Modes used:
- ``load`` — sanity-check that the tool loads and declares ``message`` arg.
- ``exec_stub_json`` — call execute with a stubbed spawnSync to verify:
  (a) success path: valid message + staged files → "Committed: <msg>",
  (b) validation errors: no scope, Cyrillic, multiline, >72, no staged,
      wrong type.

commit.ts makes up to 2 spawnSync calls: ``git diff --cached --name-only``
(staged check) and ``git commit`` (success path), or ``git log --oneline -5``
(error path appends recent commits). The stub sequencer returns responses
in order per call.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = REPO_ROOT / "tests" / "_ts_loader.mjs"
TS_FILE = REPO_ROOT / ".opencode" / "tools" / "commit.ts"
TS_FILE_REL = ".opencode/tools/commit.ts"

VALID_MSG = "feat(tools): add commit tool validation"
STAGED_RESPONSE = {"status": 0, "stdout": "file.txt\n", "stderr": ""}
COMMIT_OK_RESPONSE = {"status": 0, "stdout": "", "stderr": ""}
EMPTY_STAGED_RESPONSE = {"status": 0, "stdout": "", "stderr": ""}


def _run_loader(*args: str) -> dict:
    """Invoke the loader with TS_FILE env set to commit.ts and parse JSON stdout."""
    env = {**os.environ, "TS_FILE": TS_FILE_REL}
    proc = subprocess.run(
        ["node", str(LOADER), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
        timeout=60,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"_ts_loader.mjs {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return json.loads(proc.stdout)


def _run_exec(args: dict, responses: list[dict]) -> dict:
    """Helper: exec_stub_json mode with JSON args + sequential stub responses."""
    return _run_loader("exec_stub_json", json.dumps(args), json.dumps(responses))


def test_loader_can_load_tool():
    """Sanity: commit.ts loads and declares the message argument."""
    if not TS_FILE.exists():
        pytest.skip("commit.ts not present")
    out = _run_loader("load")
    assert "description" in out
    assert "message" in out["args"]


def test_valid_commit():
    """execute() with valid message + staged files returns 'Committed: <msg>'.

    commit.ts makes 2 spawnSync calls on the success path:
    1. git diff --cached --name-only → non-empty stdout (staged files exist)
    2. git commit -m <msg> → exit 0
    """
    out = _run_exec({"message": VALID_MSG}, [STAGED_RESPONSE, COMMIT_OK_RESPONSE])
    result = out["result"]
    assert result == f"Committed: {VALID_MSG}", f"expected success, got: {result!r}"


def test_no_scope():
    """execute() with message missing scope → error mentioning format."""
    out = _run_exec({"message": "feat: no scope here"}, [STAGED_RESPONSE])
    result = out["result"]
    assert "must match format" in result, f"expected format error, got: {result!r}"


def test_cyrillic():
    """execute() with Cyrillic in message → error mentioning English."""
    out = _run_exec({"message": "feat(тест): привет мир"}, [STAGED_RESPONSE])
    result = out["result"]
    assert "must be in English" in result, f"expected English error, got: {result!r}"


def test_multiline():
    """execute() with newline in message → error mentioning single-line."""
    out = _run_exec({"message": "feat(tools): line1\nline2"}, [STAGED_RESPONSE])
    result = out["result"]
    assert "must be single-line" in result, f"expected single-line error, got: {result!r}"


def test_too_long():
    """execute() with description >72 chars → error mentioning format."""
    long_desc = "x" * 73
    out = _run_exec({"message": f"feat(tools): {long_desc}"}, [STAGED_RESPONSE])
    result = out["result"]
    assert "must match format" in result, f"expected format error, got: {result!r}"


def test_no_staged():
    """execute() with no staged files → error mentioning 'No staged files'.

    git diff --cached returns empty stdout → tool returns error before
    reaching git commit. The error path also calls git log for recent commits,
    so we provide 2 stub responses (empty staged + log fallback).
    """
    out = _run_exec({"message": VALID_MSG}, [EMPTY_STAGED_RESPONSE, COMMIT_OK_RESPONSE])
    result = out["result"]
    assert "No staged files" in result, f"expected no-staged error, got: {result!r}"


def test_wrong_type():
    """execute() with type 'wip' (not in allowed list) → error mentioning format."""
    out = _run_exec({"message": "wip(tools): not a valid type"}, [STAGED_RESPONSE])
    result = out["result"]
    assert "must match format" in result, f"expected format error, got: {result!r}"


def test_execute_uses_cwd_from_context():
    """execute passes cwd=context.worktree to spawnSync (ADR-023 pattern).

    Like pipeline-status.ts / memory-setup.ts, the commit tool wrapper
    propagates ``context.worktree`` as ``cwd`` to spawnSync.
    """
    out = _run_exec({"message": VALID_MSG}, [STAGED_RESPONSE, COMMIT_OK_RESPONSE])
    calls = out["calls"]
    assert len(calls) >= 1, f"expected >=1 spawnSync call, got {len(calls)}"
    opts = calls[0]["opts"]
    assert opts is not None, "spawnSync called without opts — expected cwd kwarg"
    assert "cwd" in opts, f"opts missing 'cwd' key — got: {opts}"
    assert opts["cwd"] == str(REPO_ROOT), (
        f"cwd must equal context.worktree ({REPO_ROOT}), got: {opts['cwd']!r}"
    )
