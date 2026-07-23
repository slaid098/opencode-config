"""Tests for config/scripts/pipeline-status.py — pipeline oracle.

All gh/git calls are mocked via monkeypatch on the module's ``run_cmd``
helper. Filesystem checks (handoff, ADR, memory) use tmp_path.

``get_repo_full_name`` is cached via ``functools.cache`` and now called by
every ``gh pr view``/``gh pr list``/``gh issue view`` site (``--repo`` flag,
PR#101). The ``_clear_repo_cache`` autouse fixture clears the cache before
and after each test; ``mock_run_cmd`` automatically includes a ``git remote
get-url origin`` mock (``GIT_REMOTE_MOCK``) so ``get_repo_full_name()`` works
without extra boilerplate in every test.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "config" / "scripts" / "pipeline-status.py"
spec = importlib.util.spec_from_file_location("pipeline_status", SCRIPT_PATH)
ps = importlib.util.module_from_spec(spec)
sys.modules["pipeline_status"] = ps
spec.loader.exec_module(ps)

GIT_REMOTE_MOCK: tuple[tuple[str, ...], tuple[int, str, str]] = (
    ("git", "remote"),
    (0, "https://github.com/slaid098/opencode.git\n", ""),
)


@pytest.fixture(autouse=True)
def _clear_repo_cache():
    """Clear ``functools.cache`` on ``get_repo_full_name`` before/after each test.

    ``get_repo_full_name`` is now invoked by every ``gh pr view``/``gh pr list``/
    ``gh issue view`` call site (``--repo`` flag, PR#101). Without cache_clear,
    a test that mocks ``git remote`` first would leak its cached value into the
    next test.
    """
    ps.get_repo_full_name.cache_clear()
    yield
    ps.get_repo_full_name.cache_clear()


def mock_run_cmd(responses: dict[tuple, tuple[int, str, str]]):
    """Factory: mock run_cmd matching by command prefix.

    Keys are tuples of leading args (e.g. ("gh", "pr", "view")),
    values are (returncode, stdout, stderr).

    Automatically includes a ``git remote get-url origin`` mock
    (``GIT_REMOTE_MOCK``) so ``get_repo_full_name()`` works without extra
    boilerplate in every test.
    """
    merged = {GIT_REMOTE_MOCK[0]: GIT_REMOTE_MOCK[1], **responses}

    def _mock(args: list[str]) -> tuple[int, str, str]:
        for prefix, result in merged.items():
            if tuple(args[: len(prefix)]) == tuple(prefix):
                return result
        return (1, "", f"unmocked call: {args}")

    return _mock


def make_handoff(
    tmp_path: Path,
    pr_number: int,
    sections: list[str] | None = None,
    extra: str = "",
) -> Path:
    """Create a handoff file in tmp_path, return its path."""
    if sections is None:
        sections = ps.REQUIRED_SECTIONS
    content = "---\npr: {pr_number}\n---\n\n" + "\n\n".join(sections) + "\n"
    if extra:
        content += f"\n{extra}\n"
    handoff = tmp_path / f"pr-{pr_number}-test-feature.md"
    handoff.write_text(content)
    return handoff


# ── parse_remote_url ────────────────────────────────────────────────────────


def test_parse_remote_url_https():
    assert ps.parse_remote_url("https://github.com/slaid098/opencode.git") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_https_no_git_suffix():
    assert ps.parse_remote_url("https://github.com/slaid098/opencode") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_ssh():
    assert ps.parse_remote_url("git@github.com:slaid098/opencode.git") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_ssh_no_git_suffix():
    assert ps.parse_remote_url("git@github.com:slaid098/opencode") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_media_gen_https():
    """parse_remote_url для не-opencode репо (HTTPS)."""
    assert ps.parse_remote_url("https://github.com/slaid098/media-gen.git") == (
        "github.com",
        "slaid098",
        "media-gen",
    )


def test_parse_remote_url_mediakit_ssh():
    """parse_remote_url для не-opencode репо (SSH, другой org)."""
    assert ps.parse_remote_url("git@github.com:anomaly/mediakit.git") == (
        "github.com",
        "anomaly",
        "mediakit",
    )


def test_parse_remote_url_invalid():
    with pytest.raises(ValueError, match="Cannot parse remote URL"):
        ps.parse_remote_url("not-a-valid-url")


# ── check_issue ──────────────────────────────────────────────────────────────


def test_check_issue_done(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (0, '{"body": "Closes #45"}', ""),
                ("gh", "issue", "view"): (0, "issue body", ""),
            }
        ),
    )
    result = ps.check_issue(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "#45" in result.detail


def test_check_issue_not_done_no_closes(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (0, '{"body": "no closure"}', "")}),
    )
    result = ps.check_issue(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "Closes" in result.detail


def test_check_issue_not_done_pr_missing(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (1, "", "not found")}),
    )
    result = ps.check_issue(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не существует" in result.detail


def test_check_issue_ambiguous_multiple(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (0, '{"body": "Closes #45 Fixes #47"}', ""),
                ("gh", "issue", "view"): (0, "issue", ""),
            }
        ),
    )
    result = ps.check_issue(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "несколько issue" in result.detail


def test_check_issue_not_done_issue_missing(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (0, '{"body": "Closes #45"}', ""),
                ("gh", "issue", "view"): (1, "", "not found"),
            }
        ),
    )
    result = ps.check_issue(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не существует" in result.detail


# ── check_implement ──────────────────────────────────────────────────────────


def test_check_implement_done(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"files": [{"path": "docs/handoff/pr-46-test.md"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_implement(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "pr-46-test.md" in result.detail


def test_check_implement_not_done_no_handoff(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (0, '{"files": [{"path": "src/main.py"}]}', ""),
            }
        ),
    )
    result = ps.check_implement(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "handoff" in result.detail


def test_check_implement_not_done_pr_missing(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (1, "", "not found")}),
    )
    result = ps.check_implement(46)
    assert result.status == ps.PhaseStatus.NOT_DONE


# ── check_docs ───────────────────────────────────────────────────────────────


def test_check_docs_done(tmp_path, monkeypatch):
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46)
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Docs Review Summary\\nVerdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "docs-review отработал" in result.detail


def test_check_docs_not_done_no_handoff(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не найден" in result.detail


def test_check_docs_not_done_no_adr(tmp_path, monkeypatch):
    """ADR missing → DOCS phase NOT_DONE (mandatory)."""
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", tmp_path / "decisions")
    make_handoff(tmp_path, 46)
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "ADR" in result.detail


def test_check_docs_not_done_missing_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", tmp_path / "decisions")
    make_handoff(tmp_path, 46, sections=["## Что сделано", "## Почему"])
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "Pending" in result.detail
    assert "Watch out" in result.detail


def test_check_docs_done_with_adr(tmp_path, monkeypatch):
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46, extra="Архитектурное изменение, см. ADR-002.")
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Docs Review Summary\\nVerdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "docs-review отработал" in result.detail


def test_check_docs_not_done_no_comment(tmp_path, monkeypatch):
    """Handoff+ADR valid but no docs-reviewer comment → NOT_DONE."""
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46)
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (0, '{"comments": []}', "")}),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "docs-reviewer не запущен" in result.detail


def test_check_docs_not_done_comment_without_marker(tmp_path, monkeypatch):
    """Comments exist but no 'Docs Review' heading (e.g. only reviewer comment) → NOT_DONE."""
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46)
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Code Review Summary\\nVerdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "docs-reviewer не запущен" in result.detail


def test_check_docs_false_positive_reviewer_comment(tmp_path, monkeypatch):
    """Reviewer comment '## Code Review Summary' must NOT trigger check_docs DONE."""
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46)
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Code Review Summary\\n\\n### Verdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "docs-reviewer не запущен" in result.detail


def test_check_docs_ambiguous_api_error(tmp_path, monkeypatch):
    """gh pr view --json comments returns rc=1 → AMBIGUOUS."""
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46)
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (1, "", "HTTP 403: Forbidden")}),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "комментарии" in result.detail


def test_check_docs_done_with_fixed_verdict(tmp_path, monkeypatch):
    """Comment with Verdict: FIXED (docs-reviewer fixed something) → DONE."""
    adr_dir = tmp_path / "decisions"
    adr_dir.mkdir()
    (adr_dir / "002-pr-46-test.md").write_text("# ADR-002")
    monkeypatch.setattr(ps, "HANDOFF_DIR", tmp_path)
    monkeypatch.setattr(ps, "ADR_DIR", adr_dir)
    make_handoff(tmp_path, 46)
    comment_body = (
        "## Docs Review Summary\\n- Handoff: fixed: added Pending\\n\\n### Verdict: FIXED"
    )
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    f'{{"comments": [{{"body": "{comment_body}"}}]}}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_docs(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "docs-review отработал" in result.detail


# ── check_review ─────────────────────────────────────────────────────────────


def test_check_review_done(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Code Review Summary\\n\\n### Verdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "APPROVE" in result.detail


def test_check_review_not_done(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (0, '{"comments": [{"body": "changes needed"}]}', "")}),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.NOT_DONE


def test_check_review_not_done_error(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (1, "", "error")}),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.NOT_DONE


def test_check_review_false_positive_docs_reviewer_comment(monkeypatch):
    """docs-reviewer comment with '### Verdict: APPROVE' must NOT trigger check_review DONE."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Docs Review Summary\\n\\n### Verdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.NOT_DONE


def test_check_review_done_code_review_summary(monkeypatch):
    """Reviewer comment with '## Code Review Summary' + '### Verdict: APPROVE' -> DONE."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"body": "## Code Review Summary\\n\\n### Verdict: APPROVE"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.DONE


def test_check_review_not_done_approve_in_metadata(monkeypatch):
    """'approv' in author login (not body) must NOT trigger check_review."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"comments": [{"author": {"login": "approver-bot"}, "body": "LGTM"}]}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.NOT_DONE


def test_check_review_stale_approve_then_request_changes(monkeypatch):
    """Old APPROVE + new REQUEST_CHANGES -> NOT_DONE (only latest verdict counts)."""
    body1 = "## Code Review Summary\\n\\n### Verdict: APPROVE"
    body2 = "## Code Review Summary\\n\\n### Verdict: REQUEST_CHANGES"
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    f'{{"comments": [{{"body": "{body1}"}}, {{"body": "{body2}"}}]}}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "REQUEST_CHANGES" in result.detail


def test_check_review_request_changes(monkeypatch):
    """Reviewer '### Verdict: REQUEST_CHANGES' -> NOT_DONE."""
    body = "## Code Review Summary\\n\\n### Verdict: REQUEST_CHANGES"
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    f'{{"comments": [{{"body": "{body}"}}]}}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_review(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "REQUEST_CHANGES" in result.detail


# ── check_merge ──────────────────────────────────────────────────────────────


def test_check_merge_done(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (0, '{"state": "MERGED"}', "")}),
    )
    result = ps.check_merge(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "merged" in result.detail


def test_check_merge_not_done_open(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (0, '{"state": "OPEN"}', "")}),
    )
    result = ps.check_merge(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "OPEN" in result.detail


def test_check_merge_not_done_pr_missing(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("gh", "pr", "view"): (1, "", "not found")}),
    )
    result = ps.check_merge(46)
    assert result.status == ps.PhaseStatus.NOT_DONE


# ── check_memory ─────────────────────────────────────────────────────────────


def test_check_memory_done(tmp_path, monkeypatch):
    memory_file = tmp_path / "opencode.md"
    memory_file.write_text("- [2026-07-19, PR#46] test entry\n")
    monkeypatch.setattr(ps, "get_memory_file_path", lambda: memory_file)
    result = ps.check_memory(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "PR#46" in result.detail


def test_check_memory_not_done_no_file(tmp_path, monkeypatch):
    memory_file = tmp_path / "opencode.md"
    monkeypatch.setattr(ps, "get_memory_file_path", lambda: memory_file)
    result = ps.check_memory(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не существует" in result.detail


def test_check_memory_not_done_no_pattern(tmp_path, monkeypatch):
    memory_file = tmp_path / "opencode.md"
    memory_file.write_text("- some other entry\n")
    monkeypatch.setattr(ps, "get_memory_file_path", lambda: memory_file)
    result = ps.check_memory(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "не найден" in result.detail


def test_check_memory_not_done_remote_error(monkeypatch):
    monkeypatch.setattr(
        ps,
        "get_memory_file_path",
        lambda: (_ for _ in ()).throw(RuntimeError("remote error")),
    )
    result = ps.check_memory(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "remote error" in result.detail


# ── get_memory_file_path ─────────────────────────────────────────────────────


def test_get_memory_file_path(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("git", "remote"): (0, "https://github.com/slaid098/opencode.git\n", ""),
            }
        ),
    )
    path = ps.get_memory_file_path()
    assert path == ps.MEMORY_DIR / "github.com" / "slaid098" / "opencode.md"


def test_get_memory_file_path_ssh(monkeypatch):
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (0, "git@github.com:slaid098/opencode.git\n", "")}),
    )
    path = ps.get_memory_file_path()
    assert path.name == "opencode.md"
    assert "github.com" in str(path)
    assert "slaid098" in str(path)


# ── get_repo_full_name ───────────────────────────────────────────────────────


def test_get_repo_full_name_current_repo(monkeypatch):
    """get_repo_full_name возвращает org/repo из git remote (current repo)."""
    ps.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (0, "https://github.com/slaid098/opencode.git\n", "")}),
    )
    assert ps.get_repo_full_name() == "slaid098/opencode"
    ps.get_repo_full_name.cache_clear()


def test_get_repo_full_name_media_gen(monkeypatch):
    """get_repo_full_name для не-opencode репо (HTTPS)."""
    ps.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (0, "https://github.com/slaid098/media-gen.git\n", "")}),
    )
    assert ps.get_repo_full_name() == "slaid098/media-gen"
    ps.get_repo_full_name.cache_clear()


def test_get_repo_full_name_mediakit_ssh(monkeypatch):
    """get_repo_full_name для не-opencode репо (SSH, другой org)."""
    ps.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (0, "git@github.com:anomaly/mediakit.git\n", "")}),
    )
    assert ps.get_repo_full_name() == "anomaly/mediakit"
    ps.get_repo_full_name.cache_clear()


def test_get_repo_full_name_cached(monkeypatch):
    """functools.cache: second call does not hit run_cmd again."""
    ps.get_repo_full_name.cache_clear()
    call_count = [0]

    def _counting_mock(args: list[str]) -> tuple[int, str, str]:
        if tuple(args[:2]) == ("git", "remote"):
            call_count[0] += 1
            return (0, "https://github.com/slaid098/opencode.git\n", "")
        return (1, "", f"unmocked: {args}")

    monkeypatch.setattr(ps, "run_cmd", _counting_mock)
    assert ps.get_repo_full_name() == "slaid098/opencode"
    assert ps.get_repo_full_name() == "slaid098/opencode"
    assert call_count[0] == 1
    ps.get_repo_full_name.cache_clear()


def test_get_repo_full_name_remote_error(monkeypatch):
    """git remote fails → RuntimeError with explicit message."""
    ps.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (1, "", "not a git repository")}),
    )
    with pytest.raises(RuntimeError, match="Cannot get git remote URL"):
        ps.get_repo_full_name()
    ps.get_repo_full_name.cache_clear()


# ── MEMORY_DIR env var ──────────────────────────────────────────────────────


@pytest.fixture
def reload_ps_after_test():
    """Re-execute the ps module after test to restore module-level constants.

    Uses spec_from_file_location + exec_module (same as initial load) instead of
    importlib.reload — reload tries _find_spec via sys.path, which doesn't know
    about pipeline_status (loaded from a file path, not on sys.path).

    Must be listed BEFORE monkeypatch in the test signature so monkeypatch
    finalizes first (env var reverted), then this fixture re-execs ps with
    the reverted env.
    """
    yield
    _reload_ps()


def _reload_ps() -> None:
    """Re-execute the pipeline_status module from disk with current env."""
    spec = importlib.util.spec_from_file_location("pipeline_status", SCRIPT_PATH)
    spec.loader.exec_module(ps)


def test_memory_dir_uses_env_var(reload_ps_after_test, monkeypatch):
    """OPENCODE_MEMORY_DIR env var overrides default path."""
    monkeypatch.setenv("OPENCODE_MEMORY_DIR", "/custom/memory")
    _reload_ps()
    assert Path("/custom/memory") / "repos" == ps.MEMORY_DIR


def test_memory_dir_fallback_no_env_var(reload_ps_after_test, monkeypatch):
    """Without OPENCODE_MEMORY_DIR, fallback to REPO_ROOT/app_data/opencode-memory."""
    monkeypatch.delenv("OPENCODE_MEMORY_DIR", raising=False)
    _reload_ps()
    expected = ps.REPO_ROOT / "app_data" / "opencode-memory" / "repos"
    assert expected == ps.MEMORY_DIR


# ── format_single_pr (integration) ───────────────────────────────────────────


def test_format_single_pr_complete(monkeypatch):
    monkeypatch.setattr(
        ps, "run_cmd", mock_run_cmd({("gh", "pr", "view"): (0, '{"title": "test PR"}', "")})
    )
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue #1"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "docs valid"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "CI green"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "APPROVE"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "merged"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "PR#46"),
    ]
    output = ps.format_single_pr(46, results)
    assert "Status: COMPLETE" in output
    assert "PR #46" in output


def test_format_single_pr_review_not_done(monkeypatch):
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue #1"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "docs valid"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "CI green"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "APPROVE не найден"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "state=OPEN"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "PR#46 не найден"),
    ]
    monkeypatch.setattr(
        ps, "run_cmd", mock_run_cmd({("gh", "pr", "view"): (0, '{"title": "test"}', "")})
    )
    output = ps.format_single_pr(46, results)
    assert "NEXT: запустить reviewer" in output
    assert "❌" in output


def test_format_single_pr_review_request_changes(monkeypatch):
    """REVIEW not_done с verdict REQUEST_CHANGES -> NEXT про fix subagent, не re-run reviewer."""
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "docs valid"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "CI green"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "последний verdict reviewer'а: REQUEST_CHANGES"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "state=OPEN"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "PR#46 не найден"),
    ]
    monkeypatch.setattr(
        ps, "run_cmd", mock_run_cmd({("gh", "pr", "view"): (0, '{"title": "test"}', "")})
    )
    output = ps.format_single_pr(46, results)
    assert "NEXT: запусти fix subagent" in output
    assert "re-loop" in output
    assert "запустить reviewer" not in output.split("NEXT:")[1]


def test_format_single_pr_review_needs_discussion(monkeypatch):
    """REVIEW not_done с verdict NEEDS_DISCUSSION -> NEXT про уточнение, НЕ про re-run reviewer."""
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "docs valid"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "CI green"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "последний verdict reviewer'а: NEEDS_DISCUSSION"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "state=OPEN"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "PR#46 не найден"),
    ]
    monkeypatch.setattr(
        ps, "run_cmd", mock_run_cmd({("gh", "pr", "view"): (0, '{"title": "test"}', "")})
    )
    output = ps.format_single_pr(46, results)
    assert "NEXT: уточни вопросы" in output
    assert "запустить reviewer" not in output.split("NEXT:")[1]


def test_format_single_pr_memory_not_done(monkeypatch):
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue #1"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "docs valid"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "CI green"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "APPROVE"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "merged"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "PR#46 не найден в memory"),
    ]
    monkeypatch.setattr(
        ps, "run_cmd", mock_run_cmd({("gh", "pr", "view"): (0, '{"title": "test"}', "")})
    )
    output = ps.format_single_pr(46, results)
    assert "NEXT: запустить memory-syncer" in output


def test_format_single_pr_ambiguous(monkeypatch):
    results = [
        ps.PhaseResult(ps.PhaseStatus.AMBIGUOUS, "несколько issue"),
    ] + [ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "")] * 6
    monkeypatch.setattr(
        ps, "run_cmd", mock_run_cmd({("gh", "pr", "view"): (0, '{"title": "test"}', "")})
    )
    output = ps.format_single_pr(46, results)
    assert "AMBIGUOUS" in output


# ── format_table (no-args mode) ──────────────────────────────────────────────


def test_format_table_empty(monkeypatch):
    monkeypatch.setattr(ps, "list_open_pr_numbers", lambda: [])
    output = ps.format_table([])
    assert "Нет открытых PR" in output


def test_format_table_with_prs(monkeypatch):
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "docs"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "ci"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "review"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "merge"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "memory"),
    ]
    monkeypatch.setattr(ps, "run_all_checks", lambda n: results)
    monkeypatch.setattr(ps, "get_pr_title", lambda n: "test PR title")
    output = ps.format_table([47])
    assert "PR#47" in output
    assert "NEXT: запустить docs-reviewer (режим pre-merge)" in output


def test_format_pr_row_review_request_changes(monkeypatch):
    """format_pr_row (table-view): REVIEW REQUEST_CHANGES -> NEXT про fix subagent."""
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, "issue"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "handoff"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "docs valid"),
        ps.PhaseResult(ps.PhaseStatus.DONE, "CI green"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "последний verdict reviewer'а: REQUEST_CHANGES"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "state=OPEN"),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "PR#46 не найден"),
    ]
    monkeypatch.setattr(ps, "run_all_checks", lambda n: results)
    monkeypatch.setattr(ps, "get_pr_title", lambda n: "test")
    output = ps.format_pr_row(47)
    assert "NEXT: запусти fix subagent" in output
    assert "запустить reviewer" not in output.split("NEXT:")[1]


# ── get_next_action ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("ISSUE", "создать issue и связать через Closes #46 в body PR"),
        ("IMPLEMENT", "добавить handoff docs/handoff/pr-46-slug.md в diff"),
        ("DOCS", "запустить docs-reviewer (режим pre-merge)"),
        ("CI", "проверь статус CI вручную (gh run view)"),
        ("REVIEW", "запустить reviewer (task subagent_type=reviewer)"),
        ("MERGE", "смержить PR (gh pr merge 46 --squash --delete-branch)"),
        ("MEMORY", "запустить memory-syncer"),
    ],
)
def test_get_next_action(phase, expected):
    assert ps.get_next_action(phase, 46) == expected


@pytest.mark.parametrize(
    ("detail", "expected_substring"),
    [
        ("последний verdict reviewer'а: REQUEST_CHANGES", "запусти fix subagent"),
        ("последний verdict reviewer'а: NEEDS_DISCUSSION", "уточни вопросы с автором"),
        ("Code Review Summary не найден в комментариях", "запустить reviewer"),
        ("APPROVE не найден", "запустить reviewer"),
        ("нет комментариев PR", "запустить reviewer"),
    ],
)
def test_get_next_action_review(detail, expected_substring):
    result = ps.PhaseResult(ps.PhaseStatus.NOT_DONE, detail)
    assert expected_substring in ps.get_next_action_review(result)


# ── find_current_phase ───────────────────────────────────────────────────────


def test_find_current_phase_all_done():
    results = [ps.PhaseResult(ps.PhaseStatus.DONE, "")] * 7
    assert ps.find_current_phase(results) is None


def test_find_current_phase_first_not_done():
    results = [
        ps.PhaseResult(ps.PhaseStatus.DONE, ""),
        ps.PhaseResult(ps.PhaseStatus.NOT_DONE, ""),
    ] + [ps.PhaseResult(ps.PhaseStatus.NOT_DONE, "")] * 5
    assert ps.find_current_phase(results) == 1


def test_find_current_phase_skips_ambiguous():
    results = [ps.PhaseResult(ps.PhaseStatus.DONE, "")] * 6 + [
        ps.PhaseResult(ps.PhaseStatus.AMBIGUOUS, ""),
    ]
    assert ps.find_current_phase(results) == 6


# ── main ─────────────────────────────────────────────────────────────────────


def test_main_pr_not_found(monkeypatch, capsys):
    monkeypatch.setattr(ps, "check_gh_auth", lambda: None)
    monkeypatch.setattr(ps, "pr_exists", lambda n: False)
    monkeypatch.setattr("sys.argv", ["pipeline-status.py", "999"])
    with pytest.raises(SystemExit) as exc_info:
        ps.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "не существует" in captured.err


def test_main_invalid_pr_number(monkeypatch, capsys):
    monkeypatch.setattr(ps, "check_gh_auth", lambda: None)
    monkeypatch.setattr(ps, "run_cmd", mock_run_cmd({}))
    monkeypatch.setattr("sys.argv", ["pipeline-status.py", "abc"])
    with pytest.raises(SystemExit) as exc_info:
        ps.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Некорректный" in captured.err


def test_main_gh_not_authenticated(monkeypatch, capsys):
    monkeypatch.setattr(ps, "check_gh_auth", lambda: "gh CLI не авторизован")
    with pytest.raises(SystemExit) as exc_info:
        ps.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "не авторизован" in captured.err


# ── _resolve_repo_root ────────────────────────────────────────────────────────


def test_resolve_repo_root_via_git(monkeypatch, tmp_path):
    """When git rev-parse succeeds, use its output as repo root (cwd-aware)."""
    fake_root = tmp_path / "some-repo"
    fake_root.mkdir()

    class _FakeResult:
        returncode = 0
        stdout = f"{fake_root}\n"
        stderr = ""

    def fake_run(args, **kwargs):
        if tuple(args[:3]) == ("git", "rev-parse", "--show-toplevel"):
            return _FakeResult()
        raise AssertionError(f"unmocked: {args}")

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    root = ps._resolve_repo_root()
    assert root == fake_root.resolve()


def test_resolve_repo_root_fallback_to_file(monkeypatch):
    """When git rev-parse fails, fallback to Path(__file__).parent.parent.parent."""

    class _FakeResult:
        returncode = 1
        stdout = ""
        stderr = "not a git repo"

    def fake_run(args, **kwargs):
        if tuple(args[:3]) == ("git", "rev-parse", "--show-toplevel"):
            return _FakeResult()
        raise AssertionError(f"unmocked: {args}")

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    root = ps._resolve_repo_root()
    expected = Path(ps.__file__).resolve().parent.parent.parent
    assert root == expected


# ── --repo flag on gh calls (PR#101) ──────────────────────────────────────────


def test_pr_exists_with_explicit_repo(monkeypatch):
    """pr_exists passes --repo flag, so it works from non-git cwd.

    PR#101: every ``gh pr view``/``gh pr list``/``gh issue view`` call site
    appends ``--repo {get_repo_full_name()}`` (defense in depth — even if
    the TS tool wrapper fails to pass ``cwd``, the script still resolves
    the repo explicitly). This test captures the argv passed to ``run_cmd``
    and verifies ``--repo <org>/<repo>`` is present with a slash in the value.
    """
    calls: list[list[str]] = []

    def _capture(args: list[str]) -> tuple[int, str, str]:
        calls.append(args)
        return (0, '{"number": 100}', "")

    monkeypatch.setattr(ps, "run_cmd", _capture)
    ps.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ps,
        "run_cmd",
        lambda a: (
            (0, "https://github.com/slaid098/opencode.git\n", "")
            if tuple(a[:2]) == ("git", "remote")
            else _capture(a)
        ),
    )
    ps.pr_exists(100)
    assert "--repo" in calls[0]
    repo_idx = calls[0].index("--repo")
    assert "/" in calls[0][repo_idx + 1], (
        f"expected org/repo format after --repo, got: {calls[0][repo_idx + 1]!r}"
    )


def test_check_issue_uses_repo_flag(monkeypatch):
    """check_issue passes --repo to gh pr view + gh issue view, works from any cwd.

    PR#101: ``check_issue`` issues two gh calls (``gh pr view --json body``
    for the closure pattern + ``gh issue view`` for issue existence). Both
    must carry ``--repo {get_repo_full_name()}`` so they work when the
    process cwd is not a git repo.
    """
    calls: list[list[str]] = []

    def _capture(args: list[str]) -> tuple[int, str, str]:
        calls.append(args)
        if tuple(args[:3]) == ("gh", "pr", "view"):
            return (0, '{"body": "Closes #45"}', "")
        if tuple(args[:3]) == ("gh", "issue", "view"):
            return (0, "issue body", "")
        return (1, "", f"unmocked: {args}")

    monkeypatch.setattr(ps, "run_cmd", _capture)
    ps.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ps,
        "run_cmd",
        lambda a: (
            (0, "https://github.com/slaid098/opencode.git\n", "")
            if tuple(a[:2]) == ("git", "remote")
            else _capture(a)
        ),
    )
    result = ps.check_issue(46)
    assert result.status == ps.PhaseStatus.DONE
    # Two gh calls captured (pr view + issue view), each with --repo.
    gh_calls = [c for c in calls if c[0] == "gh"]
    assert len(gh_calls) == 2, f"expected 2 gh calls, got {len(gh_calls)}: {gh_calls}"
    for call in gh_calls:
        assert "--repo" in call, f"missing --repo in gh call: {call}"
        repo_idx = call.index("--repo")
        assert "/" in call[repo_idx + 1], (
            f"expected org/repo format after --repo, got: {call[repo_idx + 1]!r}"
        )
