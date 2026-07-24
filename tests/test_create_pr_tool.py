"""Tests for .opencode/tools/create-pr.ts — the create-pr custom tool.

Mirrors tests/test_pipeline_status_tool.py / test_memory_setup_tool.py:
exercises the tool's ``execute()`` function via ``tests/_ts_loader.mjs``
using the ``exec_stub_json`` mode (multi-arg tools).

The loader is parameterized via the ``TS_FILE`` env var. These tests set
``TS_FILE=.opencode/tools/create-pr.ts``.

Modes used:
- ``load`` — sanity-check that the tool loads and declares title, body,
  issue_number args.
- ``exec_stub_json`` — call execute with a stubbed spawnSync to verify:
  (a) success path: valid title + body → "PR created: <url>",
  (b) validation errors: missing scope, missing headings, Latin-only body,
  (c) issue linkage: issue_number → body gets "Closes #N" appended.

create-pr.ts makes 1 spawnSync call (gh pr create) on the success path.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = REPO_ROOT / "tests" / "_ts_loader.mjs"
TS_FILE = REPO_ROOT / ".opencode" / "tools" / "create-pr.ts"
TS_FILE_REL = ".opencode/tools/create-pr.ts"

VALID_TITLE = "feat(tools): add create-pr tool validation"
VALID_BODY = "## Что сделано\nДобавлен tool\n\n## Почему\nНужна валидация"
PR_URL = "https://github.com/slaid098/opencode-config/pull/38"
PR_OK_RESPONSE = {"status": 0, "stdout": PR_URL + "\n", "stderr": ""}


def _run_loader(*args: str) -> dict:
    """Invoke the loader with TS_FILE env set to create-pr.ts and parse JSON stdout."""
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
    """Sanity: create-pr.ts loads and declares title, body, issue_number args."""
    if not TS_FILE.exists():
        pytest.skip("create-pr.ts not present")
    out = _run_loader("load")
    assert "description" in out
    args = out["args"]
    assert "title" in args, f"missing title arg: {args}"
    assert "body" in args, f"missing body arg: {args}"
    assert "issue_number" in args, f"missing issue_number arg: {args}"


def test_valid_pr():
    """execute() with valid title + body returns 'PR created: <url>'."""
    out = _run_exec({"title": VALID_TITLE, "body": VALID_BODY}, [PR_OK_RESPONSE])
    result = out["result"]
    assert result == f"PR created: {PR_URL}", f"expected success, got: {result!r}"


def test_missing_scope():
    """execute() with title missing scope → error mentioning format."""
    out = _run_exec({"title": "feat: no scope", "body": VALID_BODY}, [PR_OK_RESPONSE])
    result = out["result"]
    assert "must match format" in result, f"expected format error, got: {result!r}"


def test_missing_chto_sdelano():
    """execute() with body missing '## Что сделано' → error mentioning heading."""
    out = _run_exec(
        {"title": VALID_TITLE, "body": "## Почему\nПотому что"},
        [PR_OK_RESPONSE],
    )
    result = out["result"]
    assert "## Что сделано" in result, f"expected heading error, got: {result!r}"


def test_missing_pochemu():
    """execute() with body missing '## Почему' → error mentioning heading."""
    out = _run_exec(
        {"title": VALID_TITLE, "body": "## Что сделано\nСделано"},
        [PR_OK_RESPONSE],
    )
    result = out["result"]
    assert "## Почему" in result, f"expected heading error, got: {result!r}"


def test_latin_only_body():
    """execute() with body containing no Cyrillic → error.

    NOTE: spec validation order checks headings (## Что сделано, ## Почему)
    BEFORE the Cyrillic check. Since the headings themselves are Cyrillic,
    a body that passes the heading checks always passes the Cyrillic check.
    Therefore a Latin-only body (no Cyrillic) also lacks the Russian headings
    and fails on the heading check first. The Cyrillic check is effectively
    dead code given the heading checks — documented as spec issue in handoff.
    This test verifies the actual reachable behavior: heading check fires.
    """
    out = _run_exec(
        {"title": VALID_TITLE, "body": "## What done\nSomething\n\n## Why\nBecause"},
        [PR_OK_RESPONSE],
    )
    result = out["result"]
    # Body lacks Russian headings → heading check fires (not Cyrillic check).
    assert "## Что сделано" in result, f"expected heading error, got: {result!r}"


def test_issue_linkage():
    """execute() with issue_number → body gets 'Closes #N' appended.

    The stub captures the spawnSync args; the --body value (index after
    --body flag) must contain 'Closes #37'.
    """
    out = _run_exec(
        {"title": VALID_TITLE, "body": VALID_BODY, "issue_number": 37},
        [PR_OK_RESPONSE],
    )
    result = out["result"]
    assert result == f"PR created: {PR_URL}", f"expected success, got: {result!r}"
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    args = calls[0]["args"]
    body_idx = args.index("--body") + 1
    body_val = args[body_idx]
    assert "Closes #37" in body_val, f"expected 'Closes #37' in body, got: {body_val!r}"


def test_execute_uses_cwd_from_context():
    """execute passes cwd=context.worktree to spawnSync (ADR-023 pattern)."""
    out = _run_exec({"title": VALID_TITLE, "body": VALID_BODY}, [PR_OK_RESPONSE])
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    opts = calls[0]["opts"]
    assert opts is not None, "spawnSync called without opts — expected cwd kwarg"
    assert "cwd" in opts, f"opts missing 'cwd' key — got: {opts}"
    assert opts["cwd"] == str(REPO_ROOT), (
        f"cwd must equal context.worktree ({REPO_ROOT}), got: {opts['cwd']!r}"
    )
