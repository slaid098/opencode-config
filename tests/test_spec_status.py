"""Tests for config/scripts/spec-status.py — spec phase oracle.

All gh/git calls are mocked via monkeypatch on the module's ``run_cmd``
helper. Filesystem checks (``docs/spec/*.md``) use ``tmp_path`` with
``monkeypatch`` on ``ss.SPEC_DIR`` and ``ss.META_FILE`` so each test sees
an isolated spec directory.

``get_repo_full_name`` is cached via ``functools.cache`` and called by
Phase 8 (``gh issue view --repo``). The ``_clear_repo_cache`` autouse
fixture clears the cache before and after each test; ``mock_run_cmd``
automatically includes a ``git remote get-url origin`` mock
(``GIT_REMOTE_MOCK``) so ``get_repo_full_name()`` works without extra
boilerplate.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "config" / "scripts" / "spec-status.py"
spec = importlib.util.spec_from_file_location("spec_status", SCRIPT_PATH)
ss = importlib.util.module_from_spec(spec)
sys.modules["spec_status"] = ss
spec.loader.exec_module(ss)

GIT_REMOTE_MOCK: tuple[tuple[str, ...], tuple[int, str, str]] = (
    ("git", "remote"),
    (0, "https://github.com/slaid098/opencode.git\n", ""),
)


@pytest.fixture(autouse=True)
def _clear_repo_cache():
    """Clear ``functools.cache`` on ``get_repo_full_name`` before/after each test."""
    ss.get_repo_full_name.cache_clear()
    yield
    ss.get_repo_full_name.cache_clear()


def mock_run_cmd(responses: dict[tuple, tuple[int, str, str]]):
    """Factory: mock run_cmd matching by command prefix.

    Keys are tuples of leading args (e.g. ("gh", "issue", "view")),
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


def _set_spec_dir(monkeypatch, tmp_path: Path) -> Path:
    """Point ``ss.SPEC_DIR`` and ``ss.META_FILE`` at ``tmp_path/spec``.

    Creates the directory so tests can drop files into it. Returns the
    spec dir path.
    """
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ss, "SPEC_DIR", spec_dir)
    monkeypatch.setattr(ss, "META_FILE", spec_dir / "meta.md")
    return spec_dir


def _write_meta(spec_dir: Path, **fields) -> None:
    """Write a ``meta.md`` frontmatter file with the given key/value pairs."""
    lines = ["---"]
    for k, v in fields.items():
        value = ("true" if v else "false") if isinstance(v, bool) else str(v)
        lines.append(f"{k}: {value}")
    lines.extend(["---", ""])
    (spec_dir / "meta.md").write_text("\n".join(lines))


# ── parse_frontmatter ────────────────────────────────────────────────────────


def test_parse_frontmatter_empty():
    assert ss.parse_frontmatter("") == {}


def test_parse_frontmatter_no_delimiters():
    assert ss.parse_frontmatter("just text\nno frontmatter") == {}


def test_parse_frontmatter_basic():
    content = "---\nproject: foo\ntype: backend\n---\nbody"
    assert ss.parse_frontmatter(content) == {"project": "foo", "type": "backend"}


def test_parse_frontmatter_quoted_values():
    content = '---\nproject: "foo bar"\ntype: "backend"\n---\n'
    fm = ss.parse_frontmatter(content)
    assert fm["project"] == '"foo bar"'
    assert fm["type"] == '"backend"'


def test_parse_frontmatter_multiline_body():
    content = "---\nproject: foo\n---\nline1\nline2\nline3\n"
    fm = ss.parse_frontmatter(content)
    assert fm == {"project": "foo"}


# ── parse_remote_url ─────────────────────────────────────────────────────────


def test_parse_remote_url_https():
    assert ss.parse_remote_url("https://github.com/slaid098/opencode.git") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_https_no_git_suffix():
    assert ss.parse_remote_url("https://github.com/slaid098/opencode") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_ssh():
    assert ss.parse_remote_url("git@github.com:slaid098/opencode.git") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_ssh_no_git_suffix():
    assert ss.parse_remote_url("git@github.com:slaid098/opencode") == (
        "github.com",
        "slaid098",
        "opencode",
    )


def test_parse_remote_url_invalid():
    with pytest.raises(ValueError, match="Cannot parse remote URL"):
        ss.parse_remote_url("not-a-valid-url")


# ── get_repo_full_name ───────────────────────────────────────────────────────


def test_get_repo_full_name_current_repo(monkeypatch):
    ss.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ss,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (0, "https://github.com/slaid098/opencode.git\n", "")}),
    )
    assert ss.get_repo_full_name() == "slaid098/opencode"
    ss.get_repo_full_name.cache_clear()


def test_get_repo_full_name_cached(monkeypatch):
    ss.get_repo_full_name.cache_clear()
    call_count = [0]

    def _counting_mock(args: list[str]) -> tuple[int, str, str]:
        if tuple(args[:2]) == ("git", "remote"):
            call_count[0] += 1
            return (0, "https://github.com/slaid098/opencode.git\n", "")
        return (1, "", f"unmocked: {args}")

    monkeypatch.setattr(ss, "run_cmd", _counting_mock)
    assert ss.get_repo_full_name() == "slaid098/opencode"
    assert ss.get_repo_full_name() == "slaid098/opencode"
    assert call_count[0] == 1
    ss.get_repo_full_name.cache_clear()


def test_get_repo_full_name_remote_error(monkeypatch):
    ss.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ss, "run_cmd", mock_run_cmd({("git", "remote"): (1, "", "not a git repository")})
    )
    with pytest.raises(RuntimeError, match="Cannot get git remote URL"):
        ss.get_repo_full_name()
    ss.get_repo_full_name.cache_clear()


# ── _resolve_repo_root ───────────────────────────────────────────────────────


def test_resolve_repo_root_via_git(monkeypatch, tmp_path):
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

    monkeypatch.setattr(ss.subprocess, "run", fake_run)
    root = ss._resolve_repo_root()
    assert root == fake_root.resolve()


def test_resolve_repo_root_fallback_to_file(monkeypatch):
    class _FakeResult:
        returncode = 1
        stdout = ""
        stderr = "not a git repo"

    def fake_run(args, **kwargs):
        if tuple(args[:3]) == ("git", "rev-parse", "--show-toplevel"):
            return _FakeResult()
        raise AssertionError(f"unmocked: {args}")

    monkeypatch.setattr(ss.subprocess, "run", fake_run)
    root = ss._resolve_repo_root()
    expected = Path(ss.__file__).resolve().parent.parent.parent
    assert root == expected


# ── file helpers ─────────────────────────────────────────────────────────────


def test_file_filled_missing(tmp_path):
    assert not ss.file_filled(tmp_path / "nope.md")


def test_file_filled_empty(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("   \n\n")
    assert not ss.file_filled(f)


def test_file_filled_ok(tmp_path):
    f = tmp_path / "ok.md"
    f.write_text("content")
    assert ss.file_filled(f)


def test_has_bullet_items_missing(tmp_path):
    assert not ss.has_bullet_items(tmp_path / "nope.md")


def test_has_bullet_items_no_bullet(tmp_path):
    f = tmp_path / "no_bullet.md"
    f.write_text("just text\nno bullets here")
    assert not ss.has_bullet_items(f)


def test_has_bullet_items_dash(tmp_path):
    f = tmp_path / "dash.md"
    f.write_text("- item one\n- item two\n")
    assert ss.has_bullet_items(f)


def test_has_bullet_items_star(tmp_path):
    f = tmp_path / "star.md"
    f.write_text("* item one\n")
    assert ss.has_bullet_items(f)


# ── check_detect (Phase 0) ───────────────────────────────────────────────────


def test_check_detect_no_meta(monkeypatch, tmp_path):
    _set_spec_dir(monkeypatch, tmp_path)
    # Ensure meta.md does not exist
    assert not (tmp_path / "spec" / "meta.md").exists()
    result = ss.check_detect()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "meta.md" in result.detail


def test_check_detect_empty_meta(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "meta.md").write_text("")
    result = ss.check_detect()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_detect_no_frontmatter(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "meta.md").write_text("just some text\nwithout frontmatter\n")
    result = ss.check_detect()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_detect_no_project_key(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, type="backend", created="2026-07-20")
    result = ss.check_detect()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "project" in result.detail


def test_check_detect_ok(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    result = ss.check_detect()
    assert result.status == ss.PhaseStatus.DONE


# ── check_project_type (Phase 1) ─────────────────────────────────────────────


def test_check_project_type_empty_type(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="")
    result = ss.check_project_type()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_project_type_invalid_type(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="unknown-type")
    result = ss.check_project_type()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "unknown-type" in result.detail


def test_check_project_type_empty_project(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="", type="backend")
    result = ss.check_project_type()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_project_type_no_context_md(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    # No context.md
    result = ss.check_project_type()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "context.md" in result.detail


def test_check_project_type_empty_context_md(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    (spec_dir / "context.md").write_text("   \n")
    result = ss.check_project_type()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_project_type_ok(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    (spec_dir / "context.md").write_text("A backend project for foo\n")
    result = ss.check_project_type()
    assert result.status == ss.PhaseStatus.DONE
    assert "backend" in result.detail


# ── check_stack (Phase 2) ────────────────────────────────────────────────────


def test_check_stack_no_stack_md(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    result = ss.check_stack()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "stack.md" in result.detail


def test_check_stack_missing_items(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    (spec_dir / "stack.md").write_text("- only fastapi\n- nothing else\n")
    result = ss.check_stack()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "tortoise" in result.detail


@pytest.mark.parametrize(
    "ptype",
    [
        "backend",
        "fullstack",
        "mcp-server",
        "cli",
        "bot",
        "worker",
    ],
)
def test_check_stack_ok_all_types(monkeypatch, tmp_path, ptype):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type=ptype)
    required = ss.STACK_REQUIRED[ptype]
    (spec_dir / "stack.md").write_text("\n".join(f"- {item}" for item in required) + "\n")
    result = ss.check_stack()
    assert result.status == ss.PhaseStatus.DONE, f"{ptype}: {result.detail}"


def test_check_stack_invalid_type(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="unknown")
    result = ss.check_stack()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "невалиден" in result.detail


def test_check_stack_case_insensitive(monkeypatch, tmp_path):
    """STACK_REQUIRED substring match is case-insensitive."""
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    (spec_dir / "stack.md").write_text(
        "- FastAPI\n- Tortoise ORM\n- UV\n- Pytest\n- Ruff\n- Mypy\n"
    )
    result = ss.check_stack()
    assert result.status == ss.PhaseStatus.DONE


# ── check_modules (Phase 3) ──────────────────────────────────────────────────


def test_check_modules_no_file(monkeypatch, tmp_path):
    _set_spec_dir(monkeypatch, tmp_path)
    result = ss.check_modules()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_modules_empty(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "modules.md").write_text("  \n\n")
    result = ss.check_modules()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_modules_no_bullet(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "modules.md").write_text("just prose\nno bullets")
    result = ss.check_modules()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_modules_ok(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "modules.md").write_text("- auth\n- users\n- posts\n")
    result = ss.check_modules()
    assert result.status == ss.PhaseStatus.DONE
    assert "3" in result.detail


# ── check_db_schema (Phase 4) ────────────────────────────────────────────────


def test_check_db_schema_no_db_true(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="cli", no_db="true")
    # db-schema.md intentionally absent
    result = ss.check_db_schema()
    assert result.status == ss.PhaseStatus.DONE
    assert "no_db" in result.detail


def test_check_db_schema_no_file(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    result = ss.check_db_schema()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_db_schema_empty(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    (spec_dir / "db-schema.md").write_text("   \n\n")
    result = ss.check_db_schema()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_db_schema_ok(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    (spec_dir / "db-schema.md").write_text("User: id, name\nPost: id, title\n")
    result = ss.check_db_schema()
    assert result.status == ss.PhaseStatus.DONE


# ── check_infra (Phase 5) ────────────────────────────────────────────────────


def test_check_infra_no_file(monkeypatch, tmp_path):
    _set_spec_dir(monkeypatch, tmp_path)
    result = ss.check_infra()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_infra_empty(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "infra.md").write_text("  \n\n")
    result = ss.check_infra()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_infra_short(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "infra.md").write_text("ab")
    result = ss.check_infra()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "<3" in result.detail


def test_check_infra_ok(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "infra.md").write_text("Docker compose, Prefect\n")
    result = ss.check_infra()
    assert result.status == ss.PhaseStatus.DONE


# ── check_roadmap (Phase 6) ──────────────────────────────────────────────────


def test_check_roadmap_no_file(monkeypatch, tmp_path):
    _set_spec_dir(monkeypatch, tmp_path)
    result = ss.check_roadmap()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_roadmap_empty(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "roadmap.md").write_text("  \n\n")
    result = ss.check_roadmap()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_roadmap_no_bullet(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "roadmap.md").write_text("just prose\nno bullets")
    result = ss.check_roadmap()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_roadmap_ok(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    (spec_dir / "roadmap.md").write_text("- scaffolding\n- auth module\n- users module\n")
    result = ss.check_roadmap()
    assert result.status == ss.PhaseStatus.DONE
    assert "3" in result.detail


# ── check_confirm (Phase 7) ──────────────────────────────────────────────────


def test_check_confirm_true(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend", confirmed="true")
    result = ss.check_confirm()
    assert result.status == ss.PhaseStatus.DONE


def test_check_confirm_false(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend", confirmed="false")
    result = ss.check_confirm()
    assert result.status == ss.PhaseStatus.NOT_DONE


def test_check_confirm_missing_key(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend")
    result = ss.check_confirm()
    assert result.status == ss.PhaseStatus.NOT_DONE


# ── check_execute (Phase 8) ──────────────────────────────────────────────────


def _setup_execute_spec(spec_dir: Path, *, executed: str = "true") -> None:
    """Write a spec where Phases 0-7 are DONE and roadmap has #N references."""
    _write_meta(
        spec_dir,
        project="foo",
        type="backend",
        confirmed="true",
        executed=executed,
    )
    (spec_dir / "roadmap.md").write_text("- #1 scaffolding\n- #2 auth\n- #3 users\n")


def test_check_execute_not_executed(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend", executed="false")
    result = ss.check_execute()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "executed" in result.detail


def test_check_execute_no_roadmap_file(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend", executed="true")
    # No roadmap.md
    result = ss.check_execute()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "roadmap.md" in result.detail


def test_check_execute_no_issue_refs(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _write_meta(spec_dir, project="foo", type="backend", executed="true")
    (spec_dir / "roadmap.md").write_text("- scaffolding\n- auth\n")  # No #N refs
    result = ss.check_execute()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "#N" in result.detail


def test_check_execute_issues_found(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _setup_execute_spec(spec_dir)
    monkeypatch.setattr(
        ss,
        "run_cmd",
        mock_run_cmd({("gh", "issue", "view"): (0, "issue body", "")}),
    )
    result = ss.check_execute()
    assert result.status == ss.PhaseStatus.DONE
    assert "3" in result.detail


def test_check_execute_issues_missing(monkeypatch, tmp_path):
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _setup_execute_spec(spec_dir)
    monkeypatch.setattr(
        ss,
        "run_cmd",
        mock_run_cmd({("gh", "issue", "view"): (1, "", "not found")}),
    )
    result = ss.check_execute()
    assert result.status == ss.PhaseStatus.NOT_DONE
    assert "#1" in result.detail
    assert "#2" in result.detail
    assert "#3" in result.detail


def test_check_execute_no_remote(monkeypatch, tmp_path):
    """git remote fails → AMBIGUOUS."""
    spec_dir = _set_spec_dir(monkeypatch, tmp_path)
    _setup_execute_spec(spec_dir)
    ss.get_repo_full_name.cache_clear()
    monkeypatch.setattr(
        ss,
        "run_cmd",
        mock_run_cmd({("git", "remote"): (1, "", "not a git repository")}),
    )
    result = ss.check_execute()
    assert result.status == ss.PhaseStatus.AMBIGUOUS
    assert "git remote error" in result.detail
    ss.get_repo_full_name.cache_clear()


# ── find_current_phase ───────────────────────────────────────────────────────


def test_find_current_phase_all_done():
    results = [ss.PhaseResult(ss.PhaseStatus.DONE, "")] * 9
    assert ss.find_current_phase(results) is None


def test_find_current_phase_first_not_done():
    results = [ss.PhaseResult(ss.PhaseStatus.NOT_DONE, "")] + [
        ss.PhaseResult(ss.PhaseStatus.DONE, "")
    ] * 8
    assert ss.find_current_phase(results) == 0


def test_find_current_phase_middle():
    results = (
        [ss.PhaseResult(ss.PhaseStatus.DONE, "")] * 3
        + [ss.PhaseResult(ss.PhaseStatus.NOT_DONE, "")]
        + [ss.PhaseResult(ss.PhaseStatus.DONE, "")] * 5
    )
    assert ss.find_current_phase(results) == 3


# ── format_output ────────────────────────────────────────────────────────────


def test_format_output_complete(monkeypatch):
    results = [ss.PhaseResult(ss.PhaseStatus.DONE, "ok")] * 9
    fm = {"project": "test-project"}
    monkeypatch.setattr("sys.argv", ["spec-status.py"])
    output = ss.format_output(results, fm)
    assert "Status: COMPLETE" in output
    assert "Spec: test-project" in output


def test_format_output_next_action(monkeypatch):
    results = (
        [ss.PhaseResult(ss.PhaseStatus.DONE, "ok")] * 3
        + [ss.PhaseResult(ss.PhaseStatus.NOT_DONE, "missing")]
        + [ss.PhaseResult(ss.PhaseStatus.NOT_DONE, "")] * 5
    )
    fm = {"project": "test-project"}
    monkeypatch.setattr("sys.argv", ["spec-status.py"])
    output = ss.format_output(results, fm)
    assert "NEXT:" in output
    assert "Phase 3" in output


def test_format_output_ambiguous(monkeypatch):
    results = (
        [ss.PhaseResult(ss.PhaseStatus.DONE, "ok")] * 2
        + [ss.PhaseResult(ss.PhaseStatus.AMBIGUOUS, "remote error")]
        + [ss.PhaseResult(ss.PhaseStatus.NOT_DONE, "")] * 6
    )
    fm = {"project": "test-project"}
    monkeypatch.setattr("sys.argv", ["spec-status.py"])
    output = ss.format_output(results, fm)
    assert "AMBIGUOUS" in output
    assert "уточните статус вручную" in output


def test_format_output_unnamed_project(monkeypatch):
    results = [ss.PhaseResult(ss.PhaseStatus.NOT_DONE, "")] * 9
    fm = {}
    monkeypatch.setattr("sys.argv", ["spec-status.py"])
    output = ss.format_output(results, fm)
    assert "Spec: <unnamed>" in output


def test_format_output_validate_shows_done_details(monkeypatch):
    """--validate flag shows full detail even for DONE phases."""
    results = [ss.PhaseResult(ss.PhaseStatus.DONE, "specific detail")] * 9
    fm = {"project": "test-project"}
    monkeypatch.setattr("sys.argv", ["spec-status.py", "--validate"])
    output = ss.format_output(results, fm)
    # In non-validate mode DONE phases show "done" only; --validate shows detail.
    assert "specific detail" in output


# ── main ─────────────────────────────────────────────────────────────────────


def test_main_no_spec(monkeypatch, tmp_path, capsys):
    """Running main() with no docs/spec/ → 9 ❌ lines + NEXT, exit 0."""
    _set_spec_dir(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.argv", ["spec-status.py"])
    ss.main()
    captured = capsys.readouterr()
    assert "Spec: <unnamed>" in captured.out
    assert "NEXT:" in captured.out
    assert "DETECT" in captured.out
