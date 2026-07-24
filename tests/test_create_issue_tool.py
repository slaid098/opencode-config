"""Tests for .opencode/tools/create-issue.ts — the create-issue custom tool.

Mirrors tests/test_pipeline_status_tool.py / test_memory_setup_tool.py:
exercises the tool's ``execute()`` function via ``tests/_ts_loader.mjs``
using the ``exec_stub_json`` mode (multi-arg tools).

The loader is parameterized via the ``TS_FILE`` env var. These tests set
``TS_FILE=.opencode/tools/create-issue.ts``.

Modes used:
- ``load`` — sanity-check that the tool loads and declares title, body,
  labels args.
- ``exec_stub_json`` — call execute with a stubbed spawnSync to verify:
  (a) success path: valid title + body → "Issue created: <url>",
  (b) validation errors: title >80, missing sections, Latin-only body,
  (c) labels: passed through to gh issue create.

create-issue.ts makes 1 spawnSync call (gh issue create) on the success path.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = REPO_ROOT / "tests" / "_ts_loader.mjs"
TS_FILE = REPO_ROOT / ".opencode" / "tools" / "create-issue.ts"
TS_FILE_REL = ".opencode/tools/create-issue.ts"

VALID_TITLE = "feat(tools): add create-issue tool validation"
VALID_BODY = (
    "## Контекст\nНужен tool\n\n## Задача\nСоздать tool\n\n## Критерии приемки\nTool работает"
)
ISSUE_URL = "https://github.com/slaid098/opencode-config/issues/39"
ISSUE_OK_RESPONSE = {"status": 0, "stdout": ISSUE_URL + "\n", "stderr": ""}


def _run_loader(*args: str) -> dict:
    """Invoke the loader with TS_FILE env set to create-issue.ts and parse JSON stdout."""
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
    """Sanity: create-issue.ts loads and declares title, body, labels args."""
    if not TS_FILE.exists():
        pytest.skip("create-issue.ts not present")
    out = _run_loader("load")
    assert "description" in out
    args = out["args"]
    assert "title" in args, f"missing title arg: {args}"
    assert "body" in args, f"missing body arg: {args}"
    assert "labels" in args, f"missing labels arg: {args}"


def test_valid_issue():
    """execute() with valid title + body returns 'Issue created: <url>'."""
    out = _run_exec({"title": VALID_TITLE, "body": VALID_BODY}, [ISSUE_OK_RESPONSE])
    result = out["result"]
    assert result == f"Issue created: {ISSUE_URL}", f"expected success, got: {result!r}"


def test_title_too_long():
    """execute() with title description >80 chars → error mentioning format.

    Issue titles allow up to 80 chars (vs 72 for commits/PRs).
    """
    long_desc = "x" * 81
    out = _run_exec({"title": f"feat(tools): {long_desc}", "body": VALID_BODY}, [ISSUE_OK_RESPONSE])
    result = out["result"]
    assert "must match format" in result, f"expected format error, got: {result!r}"


def test_title_80_chars_ok():
    """execute() with title description exactly 80 chars → success.

    Boundary check: 80 chars is the max allowed for issue titles.
    """
    desc_80 = "x" * 80
    out = _run_exec({"title": f"feat(tools): {desc_80}", "body": VALID_BODY}, [ISSUE_OK_RESPONSE])
    result = out["result"]
    assert result == f"Issue created: {ISSUE_URL}", f"expected success at boundary, got: {result!r}"


def test_missing_kontekst():
    """execute() with body missing '## Контекст' → error mentioning heading."""
    out = _run_exec(
        {
            "title": VALID_TITLE,
            "body": "## Задача\nСделать\n\n## Критерии приемки\nГотово",
        },
        [ISSUE_OK_RESPONSE],
    )
    result = out["result"]
    assert "## Контекст" in result, f"expected heading error, got: {result!r}"


def test_missing_zadacha():
    """execute() with body missing '## Задача' → error mentioning heading."""
    out = _run_exec(
        {
            "title": VALID_TITLE,
            "body": "## Контекст\nКонтекст\n\n## Критерии приемки\nГотово",
        },
        [ISSUE_OK_RESPONSE],
    )
    result = out["result"]
    assert "## Задача" in result, f"expected heading error, got: {result!r}"


def test_missing_kriterii():
    """execute() with body missing '## Критерии приемки' → error mentioning heading."""
    out = _run_exec(
        {
            "title": VALID_TITLE,
            "body": "## Контекст\nКонтекст\n\n## Задача\nСделать",
        },
        [ISSUE_OK_RESPONSE],
    )
    result = out["result"]
    assert "## Критерии приемки" in result, f"expected heading error, got: {result!r}"


def test_latin_only_body():
    """execute() with body containing no Cyrillic → error.

    NOTE: spec validation order checks headings (## Контекст, ## Задача,
    ## Критерии приемки) BEFORE the Cyrillic check. Since the headings
    themselves are Cyrillic, a body that passes the heading checks always
    passes the Cyrillic check. Therefore a Latin-only body (no Cyrillic)
    also lacks the Russian headings and fails on the heading check first.
    The Cyrillic check is effectively dead code given the heading checks —
    documented as spec issue in handoff. This test verifies the actual
    reachable behavior: heading check fires.
    """
    out = _run_exec(
        {
            "title": VALID_TITLE,
            "body": "## Context\nSome\n\n## Task\nDo it\n\n## Acceptance criteria\nDone",
        },
        [ISSUE_OK_RESPONSE],
    )
    result = out["result"]
    # Body lacks Russian headings → heading check fires (not Cyrillic check).
    assert "## Контекст" in result, f"expected heading error, got: {result!r}"


def test_labels_passed_to_gh():
    """execute() with labels → gh issue create receives --label <comma-joined>.

    The tool joins labels with a comma: ["bug", "enhancement"] → "bug,enhancement".
    """
    out = _run_exec(
        {"title": VALID_TITLE, "body": VALID_BODY, "labels": ["bug", "enhancement"]},
        [ISSUE_OK_RESPONSE],
    )
    result = out["result"]
    assert result == f"Issue created: {ISSUE_URL}", f"expected success, got: {result!r}"
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    args = calls[0]["args"]
    label_idx = args.index("--label") + 1
    label_val = args[label_idx]
    assert label_val == "bug,enhancement", f"expected comma-joined labels, got: {label_val!r}"


def test_execute_uses_cwd_from_context():
    """execute passes cwd=context.worktree to spawnSync (ADR-023 pattern)."""
    out = _run_exec({"title": VALID_TITLE, "body": VALID_BODY}, [ISSUE_OK_RESPONSE])
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    opts = calls[0]["opts"]
    assert opts is not None, "spawnSync called without opts — expected cwd kwarg"
    assert "cwd" in opts, f"opts missing 'cwd' key — got: {opts}"
    assert opts["cwd"] == str(REPO_ROOT), (
        f"cwd must equal context.worktree ({REPO_ROOT}), got: {opts['cwd']!r}"
    )
