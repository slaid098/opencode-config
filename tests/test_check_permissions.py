"""Tests for config/scripts/check-permissions.py — dangerous permission rules guard.

Covers the ``DANGEROUS_PATTERNS`` guard: clean configs pass, ``gh pr checks*``
in agent frontmatter or in ``opencode.json`` triggers a violation with the
ADR-005 reference.

Strategy:
- ``test_clean_configs_pass`` runs the script as a subprocess on the real
  (clean) repo configs — black-box, returncode 0, OK message in stdout.
- ``test_gh_pr_checks_in_agent_violation`` writes a temporary agent .md file
  into a temp ``AGENTS_DIR`` and points the script at it via monkeypatch, then
  calls ``main`` in-process and captures stdout/stderr.
- ``test_gh_pr_checks_in_opencode_json_violation`` mocks
  ``parse_global_bash_rules`` to return a rule containing ``gh pr checks*``
  and asserts ``check_rules`` flags it with the ADR-005 reference.
- ``test_gh_pr_view_statuscheckrollup_violation`` does the same for the
  narrower ``gh pr view *--json statusCheckRollup*`` pattern.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "config" / "scripts" / "check-permissions.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_permissions", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_permissions"] = module
    spec.loader.exec_module(module)
    return module


cp = _load_script()


# ── clean configs (subprocess black-box) ────────────────────────────────────


def test_clean_configs_pass():
    """On current (clean) repo configs the script exits 0 with OK message."""
    result = subprocess.run(
        ["python3", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK: No dangerous permission rules found." in result.stdout


# ── gh pr checks in agent frontmatter (in-process, tmp AGENTS_DIR) ──────────


def test_gh_pr_checks_in_agent_violation(tmp_path, monkeypatch, capsys):
    """A temp agent .md with ``"gh pr checks*": allow`` → exit 1 + ADR-005."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    agent_file = agents_dir / "test-agent.md"
    agent_file.write_text(
        "---\n"
        "description: test agent with dangerous rule\n"
        "mode: subagent\n"
        "permission:\n"
        "  bash:\n"
        '    "*": deny\n'
        '    "gh pr checks*": allow\n'
        "---\n\n"
        "# test agent\n"
    )

    monkeypatch.setattr(cp, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(cp, "OPENCODE_JSON", tmp_path / "missing-opencode.json")

    with pytest.raises(SystemExit) as exc_info:
        cp.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "gh pr checks" in captured.out
    assert "ADR-005" in captured.out
    assert "Checks API" in captured.out


# ── gh pr checks in opencode.json (mock parse_global_bash_rules) ────────────


def test_gh_pr_checks_in_opencode_json_violation(monkeypatch):
    """Mock parse_global_bash_rules returns gh pr checks* → check_rules flags it."""
    fake_rules = {"gh pr checks*": "allow"}
    monkeypatch.setattr(cp, "parse_global_bash_rules", lambda _path: fake_rules)

    violations = cp.check_rules(fake_rules, "opencode.json")
    assert len(violations) == 1
    v = violations[0]
    assert "gh pr checks" in v
    assert "ADR-005" in v
    assert "Checks API" in v


# ── gh pr view --json statusCheckRollup (mock parse_global_bash_rules) ──────


def test_gh_pr_view_statuscheckrollup_violation():
    """The narrower statusCheckRollup pattern is also flagged with ADR-005."""
    fake_rules = {"gh pr view *--json statusCheckRollup*": "allow"}
    violations = cp.check_rules(fake_rules, "opencode.json")
    assert len(violations) == 1
    v = violations[0]
    assert "statusCheckRollup" in v
    assert "ADR-005" in v
    assert "Checks API" in v


# ── deny action is not a violation ──────────────────────────────────────────


def test_deny_action_not_violation():
    """A dangerous pattern with action=deny is not flagged (only allow is)."""
    fake_rules = {"gh pr checks*": "deny"}
    violations = cp.check_rules(fake_rules, "opencode.json")
    assert violations == []


# ── gh pr merge in agent allow-list (CI guard, ADR-017) ──────────────────────


def test_gh_pr_merge_in_agent_detected(tmp_path, monkeypatch):
    """gh pr merge* in agent allow-list triggers violation (CI guard)."""
    agent_file = tmp_path / "agents" / "reviewer.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text(
        '---\nmode: subagent\npermission:\n  bash:\n    "gh pr merge*": allow\n---\ntest agent\n'
    )
    monkeypatch.setattr(cp, "AGENTS_DIR", tmp_path / "agents")
    monkeypatch.setattr(cp, "OPENCODE_JSON", tmp_path / "nonexistent.json")
    violations = cp.check_rules(
        cp.parse_agent_bash_rules(agent_file),
        f"agents/{agent_file.name}",
    )
    assert len(violations) == 1
    assert "gh pr merge*" in violations[0]
    assert "merge is done by main agent" in violations[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
