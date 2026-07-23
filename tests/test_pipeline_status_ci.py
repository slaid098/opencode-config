"""Tests for ``check_ci`` in .opencode/scripts/pipeline-status.py — CI phase.

Covers Actions API gate via ``gh api repos/<owner>/<repo>/actions/runs``.
All gh/git calls are mocked via monkeypatch on the module's ``run_cmd``
helper. ``time.sleep`` is mocked to no-op via autouse fixture (polling loop
would otherwise hang tests for up to 5 minutes).

Mocking strategy: ``check_ci`` issues calls in sequence:
1. ``gh pr view N --json headRefName`` → returns branch name JSON (once)
2. ``git remote get-url origin`` → returns remote URL (for ``get_repo_full_name``)
3. ``gh api repos/<org>/<repo>/actions/runs --jq <filter>`` → returns CI run
   JSON; may be called multiple times (polling loop / no-runs retries).

``mock_run_cmd`` dispatches by command prefix (single response per prefix).
``mock_run_cmd_seq`` supports a sequence of responses for the ``gh api``
prefix (consumed in order; last repeats if exhausted) — for polling tests.

``get_repo_full_name`` is cached via ``functools.cache`` — cleared before
each test via the ``_clear_repo_cache`` autouse fixture.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / ".opencode" / "scripts" / "pipeline-status.py"
)
spec = importlib.util.spec_from_file_location("pipeline_status_ci", SCRIPT_PATH)
ps = importlib.util.module_from_spec(spec)
sys.modules["pipeline_status_ci"] = ps
spec.loader.exec_module(ps)

GIT_REMOTE_MOCK: tuple[tuple[str, ...], tuple[int, str, str]] = (
    ("git", "remote"),
    (0, "https://github.com/slaid098/opencode-config.git\n", ""),
)


@pytest.fixture(autouse=True)
def _clear_repo_cache():
    """Clear ``functools.cache`` on ``get_repo_full_name`` + mock ``time.sleep``.

    ``time.sleep`` must be mocked — polling loop sleeps ``CI_POLL_INTERVAL``
    between queries, up to ``CI_WAIT_TIMEOUT`` (default 300s). Without mock,
    tests polling until timeout would hang for minutes.
    """
    ps.get_repo_full_name.cache_clear()
    sleep_calls: list[float] = []
    monkey = pytest.MonkeyPatch()

    def _record_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkey.setattr(ps.time, "sleep", _record_sleep)
    ps._test_sleep_calls = sleep_calls  # type: ignore[attr-defined]
    yield
    monkey.undo()
    ps.get_repo_full_name.cache_clear()
    del ps._test_sleep_calls  # type: ignore[attr-defined]


def mock_run_cmd(responses: dict[tuple, tuple[int, str, str]]):
    """Factory: mock run_cmd matching by command prefix (single response).

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


def mock_run_cmd_seq(
    pr_view: tuple[int, str, str] = (0, '{"headRefName": "feat/test-branch"}', ""),
    api_responses: list[tuple[int, str, str]] | None = None,
    extra: dict[tuple, tuple[int, str, str]] | None = None,
):
    """Factory: mock run_cmd with sequence of responses for ``gh api``.

    ``gh pr view`` returns ``pr_view`` for every call (single response).
    ``gh api`` returns ``api_responses[i]`` on the i-th call; if exhausted,
    repeats the last response (so polling loops don't run out of responses
    and hit the "unmocked" fallback). ``extra`` adds fixed overrides for
    other prefixes (e.g. ``git remote``).
    """
    api_responses = api_responses or []
    api_idx = [0]
    merged = {GIT_REMOTE_MOCK[0]: GIT_REMOTE_MOCK[1], **(extra or {})}

    def _mock(args: list[str]) -> tuple[int, str, str]:
        for prefix, result in merged.items():
            if tuple(args[: len(prefix)]) == tuple(prefix):
                return result
        if tuple(args[:3]) == ("gh", "pr", "view"):
            return pr_view
        if tuple(args[:2]) == ("gh", "api"):
            if not api_responses:
                return (1, "", "no api_responses configured")
            idx = min(api_idx[0], len(api_responses) - 1)
            api_idx[0] += 1
            return api_responses[idx]
        return (1, "", f"unmocked call: {args}")

    return _mock


# ── check_ci — completed (no polling) ──────────────────────────────────────────


def test_ci_success(monkeypatch):
    """CI run completed & success → DONE, 0 sleeps."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"headRefName": "feat/test-branch"}',
                    "",
                ),
                ("gh", "api"): (
                    0,
                    '{"status": "completed", "conclusion": "success"}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "CI green" in result.detail
    assert ps._test_sleep_calls == []  # type: ignore[attr-defined]


def test_ci_failure(monkeypatch):
    """CI run completed but conclusion=failure → NOT_DONE, 0 sleeps (don't wait for fail)."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"headRefName": "feat/test-branch"}',
                    "",
                ),
                ("gh", "api"): (
                    0,
                    '{"status": "completed", "conclusion": "failure"}',
                    "",
                ),
            }
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "failure" in result.detail
    assert ps._test_sleep_calls == []  # type: ignore[attr-defined]


# ── check_ci — polling loop ────────────────────────────────────────────────────


def test_ci_wait_then_success(monkeypatch):
    """in_progress → in_progress → completed+success → DONE, sleep called 2 times."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "in_progress", "conclusion": null}', ""),
                (0, '{"status": "in_progress", "conclusion": null}', ""),
                (0, '{"status": "completed", "conclusion": "success"}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "CI green" in result.detail
    assert len(ps._test_sleep_calls) == 2  # type: ignore[attr-defined]


def test_ci_wait_timeout(monkeypatch):
    """All calls in_progress, timeout 1s via env → AMBIGUOUS with "после 1s"."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "1")
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "in_progress", "conclusion": null}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "после 1s" in result.detail
    assert ps._test_sleep_calls == []  # type: ignore[attr-defined]


def test_ci_wait_poll_interval(monkeypatch):
    """Poll interval is used as sleep argument — capture via mock."""
    monkeypatch.setenv("OPENCODE_CI_POLL_INTERVAL", "7")
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "in_progress", "conclusion": null}', ""),
                (0, '{"status": "completed", "conclusion": "success"}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.DONE
    assert ps._test_sleep_calls == [7]  # type: ignore[attr-defined]


def test_ci_in_progress(monkeypatch):
    """status=in_progress, all polls in_progress, timeout 1s → AMBIGUOUS."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "1")
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "in_progress", "conclusion": null}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "после 1s" in result.detail


def test_ci_queued(monkeypatch):
    """status=queued, all polls in_progress, timeout 1s → AMBIGUOUS."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "1")
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "queued", "conclusion": null}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "после 1s" in result.detail


# ── check_ci — no runs (short retry) ───────────────────────────────────────────


def test_ci_no_runs_retry_then_appears(monkeypatch):
    """1st call null, 2nd null, 3rd success → DONE (after CI_NO_RUNS_RETRY retries)."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, "null", ""),
                (0, "null", ""),
                (0, '{"status": "completed", "conclusion": "success"}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.DONE
    assert "CI green" in result.detail


def test_ci_no_runs_retry_exhausted(monkeypatch):
    """All calls null, CI_NO_RUNS_RETRY=3 → AMBIGUOUS."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, "null", ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "нет CI run" in result.detail


def test_ci_no_runs(monkeypatch):
    """No CI run (jq null) with single response → AMBIGUOUS (retry exhausted)."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"headRefName": "feat/test-branch"}',
                    "",
                ),
                ("gh", "api"): (0, "null", ""),
            }
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "нет CI run" in result.detail


# ── check_ci — API error (no retry) ────────────────────────────────────────────


def test_ci_api_error(monkeypatch):
    """Actions API returns rc=1 (403) → AMBIGUOUS, no retries/sleeps."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd(
            {
                ("gh", "pr", "view"): (
                    0,
                    '{"headRefName": "feat/test-branch"}',
                    "",
                ),
                ("gh", "api"): (
                    1,
                    "",
                    "HTTP 403: Forbidden",
                ),
            }
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "Actions API" in result.detail
    assert ps._test_sleep_calls == []  # type: ignore[attr-defined]


def test_ci_api_error_no_retry(monkeypatch):
    """1st call rc=1 (403) → сразу AMBIGUOUS, 0 sleeps/retries."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (1, "", "HTTP 403: Forbidden"),
                (0, '{"status": "completed", "conclusion": "success"}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "Actions API" in result.detail
    assert ps._test_sleep_calls == []  # type: ignore[attr-defined]


# ── check_ci — config priority (CLI > env > constant) ──────────────────────────


def test_ci_wait_env_var_override(monkeypatch):
    """OPENCODE_CI_WAIT_TIMEOUT=1 → timeout 1s instead of default 300s."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "1")
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "in_progress", "conclusion": null}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "после 1s" in result.detail


def test_ci_wait_cli_flag_overrides_env(monkeypatch):
    """CLI flag --ci-wait-timeout 2 + env OPENCODE_CI_WAIT_TIMEOUT=1 → timeout 2s."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "1")

    def _fixed_config(argv=None):
        return ps.CiPollConfig(wait_timeout=2, poll_interval=ps.CI_POLL_INTERVAL)

    monkeypatch.setattr(ps, "_load_ci_config", _fixed_config)
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "in_progress", "conclusion": null}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.AMBIGUOUS
    assert "после 2s" in result.detail


def test_ci_wait_failure_no_wait(monkeypatch):
    """1st call completed+failure → сразу NOT_DONE, 0 sleeps (don't wait for fail)."""
    monkeypatch.setattr(
        ps,
        "run_cmd",
        mock_run_cmd_seq(
            api_responses=[
                (0, '{"status": "completed", "conclusion": "failure"}', ""),
            ],
        ),
    )
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.NOT_DONE
    assert "failure" in result.detail
    assert ps._test_sleep_calls == []  # type: ignore[attr-defined]


# ── check_ci — dynamic repo full name ──────────────────────────────────────────


def test_ci_uses_dynamic_repo_full_name(monkeypatch):
    """``get_repo_full_name`` is derived from ``git remote``, not hardcoded.

    Mocks a non-opencode remote (``slaid098/media-gen``) and asserts that the
    ``gh api`` call uses ``repos/slaid098/media-gen/actions/runs`` (dynamic),
    not a hardcoded ``slaid098/opencode-config``.
    """
    captured_args: list[list[str]] = []

    def _capture_mock(args: list[str]) -> tuple[int, str, str]:
        captured_args.append(args)
        if tuple(args[:3]) == ("git", "remote", "get-url"):
            return (0, "https://github.com/slaid098/media-gen.git\n", "")
        if tuple(args[:3]) == ("gh", "pr", "view"):
            return (0, '{"headRefName": "feat/test-branch"}', "")
        if tuple(args[:2]) == ("gh", "api"):
            return (0, '{"status": "completed", "conclusion": "success"}', "")
        return (1, "", f"unmocked call: {args}")

    monkeypatch.setattr(ps, "run_cmd", _capture_mock)
    result = ps.check_ci(46)
    assert result.status == ps.PhaseStatus.DONE

    api_calls = [a for a in captured_args if a[:2] == ["gh", "api"]]
    assert len(api_calls) == 1
    assert "repos/slaid098/media-gen/actions/runs" in " ".join(api_calls[0])
    assert "slaid098/opencode-config" not in " ".join(api_calls[0])


# ── _load_ci_config — priority ────────────────────────────────────────────────


def test_load_ci_config_defaults(monkeypatch):
    """No env, no CLI → constants."""
    monkeypatch.delenv("OPENCODE_CI_WAIT_TIMEOUT", raising=False)
    monkeypatch.delenv("OPENCODE_CI_POLL_INTERVAL", raising=False)
    cfg = ps._load_ci_config(argv=[])
    assert cfg.wait_timeout == ps.CI_WAIT_TIMEOUT
    assert cfg.poll_interval == ps.CI_POLL_INTERVAL


def test_load_ci_config_env_override(monkeypatch):
    """Env vars override constants."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "42")
    monkeypatch.setenv("OPENCODE_CI_POLL_INTERVAL", "7")
    cfg = ps._load_ci_config(argv=[])
    assert cfg.wait_timeout == 42
    assert cfg.poll_interval == 7


def test_load_ci_config_cli_overrides_env(monkeypatch):
    """CLI flags override env vars."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "1")
    monkeypatch.setenv("OPENCODE_CI_POLL_INTERVAL", "1")
    cfg = ps._load_ci_config(argv=["--ci-wait-timeout", "2", "--ci-poll-interval", "3"])
    assert cfg.wait_timeout == 2
    assert cfg.poll_interval == 3


def test_load_ci_config_env_invalid_falls_back(monkeypatch):
    """Invalid env var value → fall back to constant."""
    monkeypatch.setenv("OPENCODE_CI_WAIT_TIMEOUT", "not-a-number")
    cfg = ps._load_ci_config(argv=[])
    assert cfg.wait_timeout == ps.CI_WAIT_TIMEOUT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
