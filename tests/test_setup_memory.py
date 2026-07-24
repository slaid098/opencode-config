"""Tests for .opencode/scripts/setup-memory.sh — deterministic memory init.

Uses a local mock remote (``git init --bare``) instead of GitHub so the
tests are hermetic and offline-safe. ``tmp_path`` provides isolation.

The script is invoked via ``subprocess`` with env vars pointing at the
mock remote + a tmp dir. Each test asserts one of the 6 deterministic
flow steps.

Script contract (``setup-memory.sh``):
  1. mkdir -p MEMORY_DIR
  2. clone REMOTE | git pull --ff-only
  3. remote set-url if origin != REMOTE
  4. install post-commit hook (auto-push) if missing/wrong
  5. rag index if .rag missing (best-effort, rag optional)
  6. echo status

Exit 1 when ``OPENCODE_MEMORY_REMOTE`` is unset (no default — the
``.env.example`` provides the value; absence is a config error).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / ".opencode" / "scripts" / "setup-memory.sh"

EXPECTED_HOOK = "#!/bin/bash\ngit push origin master 2>/dev/null || true\n"


def _seed_remote(remote_dir: Path) -> None:
    """Seed a bare remote with one commit on ``master``."""
    remote_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", "-q", str(remote_dir)], check=True)
    seed = remote_dir.parent / "seed"
    seed.mkdir()
    subprocess.run(["git", "init", "-q", str(seed)], check=True)
    (seed / "README.md").write_text("# memory\n")
    subprocess.run(["git", "-C", str(seed), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(seed),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "init",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(seed), "branch", "-M", "master"], check=True)
    subprocess.run(
        ["git", "-C", str(seed), "remote", "add", "origin", str(remote_dir)],
        check=True,
    )
    subprocess.run(["git", "-C", str(seed), "push", "-q", "origin", "master"], check=True)


def _run_script(memory_dir: Path, remote: str | None) -> subprocess.CompletedProcess:
    """Run setup-memory.sh with env pointing at tmp paths.

    When ``remote`` is None, OPENCODE_MEMORY_REMOTE is removed from env
    (simulating the "no remote env" error path).
    """
    env = {
        **os.environ,
        "OPENCODE_MEMORY_DIR": str(memory_dir),
        "GIT_TERMINAL_PROMPT": "0",
    }
    if remote is not None:
        env["OPENCODE_MEMORY_REMOTE"] = remote
    else:
        env.pop("OPENCODE_MEMORY_REMOTE", None)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_fresh_init(tmp_path: Path) -> None:
    """Empty dir → run → clone, hook, remote, files present."""
    remote = tmp_path / "remote.git"
    _seed_remote(remote)
    mem = tmp_path / "mem"
    r = _run_script(mem, str(remote))
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert (mem / ".git").is_dir(), "repo not cloned"
    assert (mem / "README.md").exists(), "file not pulled"
    assert (mem / ".git" / "hooks" / "post-commit").exists(), "hook missing"
    got = subprocess.run(
        ["git", "-C", str(mem), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert got == str(remote), f"remote mismatch: {got}"


def test_existing_repo(tmp_path: Path) -> None:
    """.git exists → run → pull --ff-only, no destructive changes."""
    remote = tmp_path / "remote.git"
    _seed_remote(remote)
    mem = tmp_path / "mem"
    assert _run_script(mem, str(remote)).returncode == 0
    # capture state before second run
    head_before = subprocess.run(
        ["git", "-C", str(mem), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    r = _run_script(mem, str(remote))
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    head_after = subprocess.run(
        ["git", "-C", str(mem), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_before == head_after, "pull --ff-only changed HEAD unexpectedly"
    assert "pulling latest" in r.stdout


def test_wrong_remote(tmp_path: Path) -> None:
    """remote ≠ expected → run → set-url corrects the remote."""
    remote = tmp_path / "remote.git"
    _seed_remote(remote)
    mem = tmp_path / "mem"
    assert _run_script(mem, str(remote)).returncode == 0
    # corrupt remote URL (tmp path — avoids S108 insecure-tmp warning)
    wrong = tmp_path / "wrong-remote"
    subprocess.run(
        ["git", "-C", str(mem), "remote", "set-url", "origin", str(wrong)],
        check=True,
    )
    r = _run_script(mem, str(remote))
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "fixing remote" in r.stdout
    got = subprocess.run(
        ["git", "-C", str(mem), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert got == str(remote), f"remote not fixed: {got}"


def test_missing_hook(tmp_path: Path) -> None:
    """hook missing → run → hook created with correct content."""
    remote = tmp_path / "remote.git"
    _seed_remote(remote)
    mem = tmp_path / "mem"
    assert _run_script(mem, str(remote)).returncode == 0
    hook = mem / ".git" / "hooks" / "post-commit"
    hook.unlink()
    assert not hook.exists()
    r = _run_script(mem, str(remote))
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert hook.exists(), "hook not recreated"
    assert hook.read_text() == EXPECTED_HOOK, f"hook content wrong: {hook.read_text()!r}"
    assert "installing post-commit hook" in r.stdout


def test_idempotent(tmp_path: Path) -> None:
    """run 3x → state identical after run 1 and run 3."""
    remote = tmp_path / "remote.git"
    _seed_remote(remote)
    mem = tmp_path / "mem"

    def _snapshot() -> dict:
        head = subprocess.run(
            ["git", "-C", str(mem), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        hook = mem / ".git" / "hooks" / "post-commit"
        return {
            "head": head,
            "hook": hook.read_text() if hook.exists() else None,
            "remote": subprocess.run(
                ["git", "-C", str(mem), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip(),
        }

    assert _run_script(mem, str(remote)).returncode == 0
    snap1 = _snapshot()
    assert _run_script(mem, str(remote)).returncode == 0
    assert _run_script(mem, str(remote)).returncode == 0
    snap3 = _snapshot()
    assert snap1 == snap3, f"non-idempotent:\n  run1={snap1}\n  run3={snap3}"


def test_no_remote_env(tmp_path: Path) -> None:
    """OPENCODE_MEMORY_REMOTE unset → exit 1, error message to stderr/stdout."""
    mem = tmp_path / "mem"
    r = _run_script(mem, remote=None)
    assert r.returncode == 1, f"expected exit 1, got {r.returncode}"
    combined = r.stderr + r.stdout
    assert "OPENCODE_MEMORY_REMOTE" in combined, f"missing error msg: {combined!r}"
    assert "ERROR" in combined or "not set" in combined


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
