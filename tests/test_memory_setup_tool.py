"""Tests for .opencode/tools/memory-setup.ts — the memory-setup custom tool.

Mirrors ``tests/test_pipeline_status_tool.py`` / ``test_spec_status_tool.py``:
exercises the tool's ``execute()`` function via ``tests/_ts_loader.mjs``
(a node CommonJS sandbox that strips TS-only syntax, stubs
``@opencode-ai/plugin``, and replaces ``import.meta.dir`` with the real
``.opencode/tools`` directory).

The loader is parameterized via the ``TS_FILE`` env var so the same harness
works for every TS tool wrapper. These tests set
``TS_FILE=.opencode/tools/memory-setup.ts``.

Modes used (same as the pipeline-status / spec-status tool tests):
- ``load`` — sanity-check that the tool loads and declares no args.
- ``exec_stub`` — call execute with a stubbed spawnSync to verify:
  (a) success path: exit 0 → trimmed stdout returned,
  (b) failure path: exit 1 → ``⚠️ memory-setup failed (exit 1): <stderr>``.
- ``exec_real`` — call execute against the real setup-memory.sh
  (integration, requires OPENCODE_MEMORY_REMOTE + a reachable remote;
  skipped if env not set).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = REPO_ROOT / "tests" / "_ts_loader.mjs"
TS_FILE = REPO_ROOT / ".opencode" / "tools" / "memory-setup.ts"
TS_FILE_REL = ".opencode/tools/memory-setup.ts"


def _run_loader(*args: str) -> dict:
    """Invoke the loader with ``TS_FILE`` env set to memory-setup.ts and parse JSON stdout."""
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


def test_loader_can_load_tool():
    """Sanity: memory-setup.ts loads and declares no args (toggle-style tool)."""
    if not TS_FILE.exists():
        pytest.skip("memory-setup.ts not present")
    out = _run_loader("load")
    assert "description" in out
    assert out["args"] == [], f"expected no args, got: {out['args']}"


def test_success():
    """execute() with exit 0 returns trimmed stdout.

    memory-setup.ts follows the tunnel.ts pattern: ``r.stdout.trim()`` on
    success. Stub spawnSync to return ``"  memory: ready  \\n"`` and verify
    the tool returns ``"memory: ready"`` (whitespace stripped).
    """
    out = _run_loader("exec_stub", "_", "0", "  memory: ready  \n", "")
    result = out["result"]
    assert result == "memory: ready", f"expected trimmed stdout, got: {result!r}"


def test_failure():
    """execute() with exit 1 returns ``⚠️ memory-setup failed (exit 1): <stderr>``.

    The tool prepends ``⚠️ memory-setup failed (exit <N>): `` to the stderr
    (falling back to stdout if stderr is empty). Stub spawnSync to return
    exit 1 + a stderr string and verify the error prefix + stderr content.
    """
    out = _run_loader("exec_stub", "_", "1", "", "ERROR: OPENCODE_MEMORY_REMOTE not set")
    result = out["result"]
    assert "⚠️ memory-setup failed" in result, f"missing error prefix: {result!r}"
    assert "exit 1" in result, f"missing exit code: {result!r}"
    assert "OPENCODE_MEMORY_REMOTE not set" in result, f"missing stderr: {result!r}"


def test_execute_uses_cwd_from_context():
    """execute passes ``cwd=context.worktree`` to spawnSync (ADR-023 pattern).

    Like pipeline-status.ts / spec-status.ts / tunnel.ts, the memory-setup
    tool wrapper propagates ``context.worktree`` as ``cwd`` to spawnSync so
    the bash script runs in the git worktree root (where .opencode/ lives),
    not in the opencode process cwd.
    """
    out = _run_loader("exec_stub", "_", "0", "ok", "")
    calls = out["calls"]
    assert len(calls) == 1, f"expected 1 spawnSync call, got {len(calls)}"
    opts = calls[0]["opts"]
    assert opts is not None, "spawnSync called without opts — expected cwd kwarg"
    assert "cwd" in opts, f"opts missing 'cwd' key — got: {opts}"
    assert opts["cwd"] == str(REPO_ROOT), (
        f"cwd must equal context.worktree ({REPO_ROOT}), got: {opts['cwd']!r}"
    )
