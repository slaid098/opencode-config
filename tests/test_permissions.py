"""Tests for global deny rules and role-based tool access in ``.opencode/opencode.json``.

Covers issue #39 acceptance criteria:
- Global ``permission.bash`` deny rules for direct ``git commit``/``gh pr create``/
  ``gh pr merge``/``gh issue create`` (findLast — last wins, so they override earlier
  allows).
- ``agent.<name>.tools`` role-based access map per subagent.
- ``check-permissions.py`` exits 0 on the real repo configs.

Strategy:
- ``test_*_present`` load the real ``.opencode/opencode.json`` and assert structure.
- ``test_check_permissions_passes`` runs the validator as a subprocess (black-box).
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENCODE_JSON = REPO_ROOT / ".opencode" / "opencode.json"
CHECK_PERM_SCRIPT = REPO_ROOT / ".opencode" / "scripts" / "check-permissions.py"


def _load_config() -> dict:
    with open(OPENCODE_JSON) as f:
        return json.load(f)


# ── global deny rules ───────────────────────────────────────────────────────


def test_global_deny_rules_present():
    """The 4 deny rules exist in permission.bash and are set to 'deny'."""
    bash = _load_config()["permission"]["bash"]
    expected = {
        "git commit *": "deny",
        "gh pr create *": "deny",
        "gh pr merge *": "deny",
        "gh issue create *": "deny",
    }
    for pattern, action in expected.items():
        assert pattern in bash, f"missing deny rule: {pattern}"
        assert bash[pattern] == action, f"{pattern}: expected {action}, got {bash[pattern]}"


def test_git_push_remains_allowed():
    """git push must NOT be denied (issue constraint)."""
    bash = _load_config()["permission"]["bash"]
    assert bash.get("git push *") == "allow", "git push must remain allowed"


def test_deny_rules_override_earlier_allows():
    """findLast semantics: deny rules come AFTER earlier allows, so deny wins.

    For ``git commit *`` the allow and deny use the same pattern — JSON dedupes
    keys, so ``json.load`` keeps the last value (deny). For the other 3 the deny
    pattern is narrower (e.g. ``gh pr create *`` vs ``gh pr create*``) and appears
    later in insertion order. This test verifies ordering for the differing
    patterns and final value for the duplicate-key case.
    """
    bash = _load_config()["permission"]["bash"]
    keys = list(bash.keys())

    # git commit *: same pattern for allow+deny, json.load keeps last (deny).
    assert bash["git commit *"] == "deny"

    # The other 3: deny pattern must appear after the broader allow pattern.
    ordering_checks = [
        ("gh pr create*", "gh pr create *"),
        ("gh pr merge*", "gh pr merge *"),
        ("gh issue*", "gh issue create *"),
    ]
    for allow_pattern, deny_pattern in ordering_checks:
        if allow_pattern in keys and deny_pattern in keys:
            assert keys.index(deny_pattern) > keys.index(allow_pattern), (
                f"deny '{deny_pattern}' must come after allow '{allow_pattern}' "
                f"(findLast: last wins)"
            )


# ── agent.general.tools ────────────────────────────────────────────────────


def test_general_tools():
    """general: commit/create_pr/create_issue=true, merge_pr=false."""
    tools = _load_config()["agent"]["general"]["tools"]
    assert tools["commit"] is True
    assert tools["create_pr"] is True
    assert tools["create_issue"] is True
    assert tools["merge_pr"] is False
    assert _load_config()["agent"]["general"]["steps"] == 100


# ── agent.reviewer.tools ────────────────────────────────────────────────────


def test_reviewer_tools_all_false():
    """reviewer is read-only — all 4 tools false."""
    tools = _load_config()["agent"]["reviewer"]["tools"]
    assert tools["commit"] is False
    assert tools["create_pr"] is False
    assert tools["create_issue"] is False
    assert tools["merge_pr"] is False


# ── agent.docs-reviewer.tools ───────────────────────────────────────────────


def test_docs_reviewer_tools():
    """docs-reviewer: commit=true (commits project map/handoff), rest false."""
    tools = _load_config()["agent"]["docs-reviewer"]["tools"]
    assert tools["commit"] is True
    assert tools["create_pr"] is False
    assert tools["create_issue"] is False
    assert tools["merge_pr"] is False


# ── agent.memory-syncer.tools ───────────────────────────────────────────────


def test_memory_syncer_tools_all_false():
    """memory-syncer works only in memory repo — all 4 tools false."""
    tools = _load_config()["agent"]["memory-syncer"]["tools"]
    assert tools["commit"] is False
    assert tools["create_pr"] is False
    assert tools["create_issue"] is False
    assert tools["merge_pr"] is False


# ── check-permissions.py passes ─────────────────────────────────────────────


def test_check_permissions_passes():
    """The validator exits 0 with OK message on current configs."""
    result = subprocess.run(
        ["python3", str(CHECK_PERM_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK: No dangerous permission rules found." in result.stdout


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
