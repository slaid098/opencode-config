"""Tests for .opencode/scripts/observability.py — log parser for denials/errors.

Pattern: direct calls for parse_line/_process_line, tmp_path + monkeypatch on
obs.LOG_PATH for main() tests. Loading via importlib.util.spec_from_file_location
(same pattern as test_pipeline_status.py / test_spec_status.py).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / ".opencode" / "scripts" / "observability.py"
spec = importlib.util.spec_from_file_location("observability", SCRIPT_PATH)
obs = importlib.util.module_from_spec(spec)
sys.modules["observability"] = obs
spec.loader.exec_module(obs)


# ── parse_line ──────────────────────────────────────────────────────────────


def test_parse_line_with_timestamp_and_run():
    assert obs.parse_line("timestamp=2026-07-20T10:00:00 run=abc123") == (
        "2026-07-20T10:00:00",
        "abc123",
    )


def test_parse_line_no_timestamp():
    assert obs.parse_line("run=abc123") == ("?", "abc123")


def test_parse_line_no_run():
    assert obs.parse_line("timestamp=2026-07-20T10:00:00") == (
        "2026-07-20T10:00:00",
        "?",
    )


def test_parse_line_no_matches():
    assert obs.parse_line("random line") == ("?", "?")


def test_parse_line_empty():
    assert obs.parse_line("") == ("?", "?")


# ── _process_line: sessions ──────────────────────────────────────────────────


def test_process_line_session_created():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        'message=created agent=build run=abc id=sess1 title="Test"',
        sessions,
        denials,
        errors,
    )
    assert sessions == {"abc": {"agent": "build", "session": "sess1", "title": "Test"}}
    assert denials == []
    assert errors == []


def test_process_line_session_no_agent():
    # `agent=` present but value empty — `agent=(\S+)` regex misses → fallback "unknown".
    # NOTE: spec issue #111 used `message=created run=abc id=sess1` (no `agent=` at all),
    # but `observability.py:23` requires `"agent=" in line` to enter the session branch.
    # Fix: `agent=` with empty value exercises the `unknown` fallback (the spec's intent).
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=created agent= run=abc id=sess1",
        sessions,
        denials,
        errors,
    )
    assert sessions == {"abc": {"agent": "unknown", "session": "sess1", "title": ""}}


def test_process_line_session_no_title():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=created agent=build run=abc id=sess1",
        sessions,
        denials,
        errors,
    )
    assert sessions == {"abc": {"agent": "build", "session": "sess1", "title": ""}}


# ── _process_line: denials ───────────────────────────────────────────────────


def test_process_line_denial():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        'action.action=deny run=abc pattern="rm *" permission=bash',
        sessions,
        denials,
        errors,
    )
    assert len(denials) == 1
    d = denials[0]
    assert d["run"] == "abc"
    assert d["pattern"] == "rm *"
    assert d["perm"] == "bash"
    assert d["ts"] == "?"
    assert sessions == {}
    assert errors == []


def test_process_line_denial_no_pattern():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "action.action=deny run=abc permission=bash",
        sessions,
        denials,
        errors,
    )
    assert len(denials) == 1
    assert denials[0]["pattern"] == "?"


# ── _process_line: errors ─────────────────────────────────────────────────────


def test_process_line_error():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=process level=ERROR run=abc error=ToolExecFailed session.id=sess1",
        sessions,
        denials,
        errors,
    )
    assert len(errors) == 1
    e = errors[0]
    assert e["run"] == "abc"
    assert e["error"] == "ToolExecFailed"
    assert e["session"] == "sess1"
    assert e["ts"] == "?"
    assert sessions == {}
    assert denials == []


def test_process_line_error_no_session():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=process level=ERROR run=abc error=ToolExecFailed",
        sessions,
        denials,
        errors,
    )
    assert len(errors) == 1
    assert errors[0]["session"] == "?"


def test_process_line_error_no_error_field():
    """No error= field → error default 'unknown'."""
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=process level=ERROR run=abc session.id=sess1",
        sessions,
        denials,
        errors,
    )
    assert len(errors) == 1
    assert errors[0]["error"] == "unknown"


# ── _process_line: unmatched ──────────────────────────────────────────────────


def test_process_line_unmatched():
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line("random log line", sessions, denials, errors)
    assert sessions == {}
    assert denials == []
    assert errors == []


def test_process_line_message_process_no_error():
    """message=process without level=ERROR → not classified as error."""
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=process level=INFO run=abc",
        sessions,
        denials,
        errors,
    )
    assert sessions == {}
    assert denials == []
    assert errors == []


def test_process_line_created_without_agent_keyword():
    """message=created present but no 'agent=' substring → not a session line."""
    sessions: dict = {}
    denials: list = []
    errors: list = []
    obs._process_line(
        "message=created run=abc id=sess1",
        sessions,
        denials,
        errors,
    )
    # 'message=created' in line AND 'agent=' in line — second condition fails,
    # so falls through. No 'action.action=deny' or 'message=process level=ERROR'.
    assert sessions == {}
    assert denials == []
    assert errors == []


# ── main ─────────────────────────────────────────────────────────────────────


def test_main_no_log_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(obs, "LOG_PATH", tmp_path / "nonexistent.log")
    with pytest.raises(SystemExit) as exc_info:
        obs.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Log file not found" in captured.out


def test_main_empty_log(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    log_file.write_text("")
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    assert "No denials or errors found in log." in captured.out


def test_main_only_sessions(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    log_file.write_text('message=created agent=build run=abc id=sess1 title="Test"\n')
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    assert "No denials or errors found in log." in captured.out


def test_main_with_denials(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    log_file.write_text('action.action=deny run=abc pattern="rm *" permission=bash\n')
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    assert "## Permission Denials" in captured.out
    assert "`rm *`" in captured.out
    assert "bash" in captured.out
    assert "unknown" in captured.out  # agent lookup falls back to unknown


def test_main_with_errors(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "message=process level=ERROR run=abc error=ToolExecFailed session.id=sess1\n"
    )
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    assert "## Process Errors" in captured.out
    assert "ToolExecFailed" in captured.out
    assert "sess1" in captured.out


def test_main_mixed(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        'message=created agent=build run=abc id=sess1 title="Test"\n'
        'action.action=deny run=abc pattern="rm *" permission=bash\n'
        "message=process level=ERROR run=abc error=ToolExecFailed session.id=sess1\n"
    )
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    assert "# Observability Report" in captured.out
    assert "## Permission Denials" in captured.out
    assert "### build (1 denials)" in captured.out
    assert "## Process Errors" in captured.out
    # Denial row references session from sessions dict.
    assert "sess1" in captured.out


def test_main_denials_grouped_by_agent(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        'message=created agent=zebra run=r1 id=s1 title="A"\n'
        'message=created agent=alpha run=r2 id=s2 title="B"\n'
        'action.action=deny run=r1 pattern="p1" permission=bash\n'
        'action.action=deny run=r2 pattern="p2" permission=edit\n'
    )
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    out = captured.out
    # sorted alphabetically by agent
    alpha_idx = out.find("### alpha")
    zebra_idx = out.find("### zebra")
    assert alpha_idx != -1
    assert zebra_idx != -1
    assert alpha_idx < zebra_idx


def test_main_errors_last_20(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "test.log"
    lines = []
    for i in range(25):
        lines.append(f"message=process level=ERROR run=run{i} error=Err{i} session.id=s{i}\n")
    log_file.write_text("".join(lines))
    monkeypatch.setattr(obs, "LOG_PATH", log_file)
    obs.main()
    captured = capsys.readouterr()
    out = captured.out
    # Last 20 of 25 errors: indices 5..24 → Err5..Err24
    assert "Err24" in out
    assert "Err5" in out
    assert "Err4" not in out  # not in last 20
    assert "Err0" not in out
