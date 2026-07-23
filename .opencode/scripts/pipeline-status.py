#!/usr/bin/env python3
"""Pipeline-status oracle: determine PR phase in 7-phase PR pipeline.

Reads facts from GitHub (gh CLI), git, and memory files to deterministically
derive the current pipeline phase of a PR — no state file, like ``git status``
for the PR pipeline. CI gate via Actions API (read-only): CI ❌ blocks MERGE
(transitive guard — first ❌ phase blocks all subsequent phases).

Usage:
    python3 config/scripts/pipeline-status.py <PR_NUMBER>   # single PR status
    python3 config/scripts/pipeline-status.py               # table of open PRs

Seven phases:
    1. ISSUE      — GitHub issue exists and linked via Closes/Fixes #N
    2. IMPLEMENT  — PR exists + handoff file docs/handoff/pr-N-slug.md in diff
    3. DOCS       — handoff valid (4 sections) + mandatory ADR
    4. CI         — latest CI run on PR branch completed & success
    5. REVIEW     — APPROVE found in PR comments
    6. MERGE      — PR state is MERGED
    7. MEMORY     — PR#N distilled into repos/{host}/{org}/{repo}.md
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


def _resolve_repo_root() -> Path:
    """Resolve repo root via git (cwd-aware), fallback to script location."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return Path(__file__).resolve().parent.parent.parent


REPO_ROOT = _resolve_repo_root()
_MEMORY_BASE = os.environ.get(
    "OPENCODE_MEMORY_DIR",
    str(REPO_ROOT / "app_data" / "opencode-memory"),
)
MEMORY_DIR = Path(_MEMORY_BASE) / "repos"
HANDOFF_DIR = REPO_ROOT / "docs" / "handoff"
ADR_DIR = REPO_ROOT / "docs" / "decisions"

REQUIRED_SECTIONS = ["## Что сделано", "## Почему", "## Pending", "## Watch out"]

PHASE_NAMES = ["ISSUE", "IMPLEMENT", "DOCS", "CI", "REVIEW", "MERGE", "MEMORY"]

CI_WAIT_TIMEOUT = 300
CI_POLL_INTERVAL = 10
CI_NO_RUNS_RETRY = 3
CI_NO_RUNS_INTERVAL = 5

CLOSURE_RE = re.compile(r"(?:Closes|Fixes|Resolves)\s+#(\d+)", re.IGNORECASE)
REVIEW_APPROVE_RE = re.compile(
    r"## Code Review Summary.*?###\s*Verdict:\s*APPROVE\b",
    re.IGNORECASE | re.DOTALL,
)
REVIEW_VERDICT_RE = re.compile(
    r"## Code Review Summary.*?###\s*Verdict:\s*(\w+)",
    re.IGNORECASE | re.DOTALL,
)
DOCS_REVIEW_RE = re.compile(r"Docs Review", re.IGNORECASE)
JSON_FIELD_RE = re.compile(r'"(\w+)"\s*:\s*"?([^",}]*)"?', re.IGNORECASE)


class PhaseStatus(StrEnum):
    """Phase check result."""

    DONE = "DONE"
    NOT_DONE = "NOT_DONE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class PhaseResult:
    """Result of a single phase check."""

    status: PhaseStatus
    detail: str


def run_cmd(args: list[str]) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout, result.stderr


@dataclass(frozen=True)
class CiPollConfig:
    """CI polling parameters.

    Priority: CLI flag > env var > constant in code.
    """

    wait_timeout: int
    poll_interval: int


def _env_int(name: str, default: int) -> int:
    """Read int from env var, fallback to default on missing/invalid."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_ci_config(argv: list[str] | None = None) -> CiPollConfig:
    """Build CiPollConfig from CLI flags + env vars + constants.

    Priority: CLI flag > env var > constant. CLI flags ``--ci-wait-timeout N``
    and ``--ci-poll-interval N`` parsed manually from ``argv`` (last wins).
    """
    args = argv if argv is not None else sys.argv[1:]
    cli_timeout: int | None = None
    cli_interval: int | None = None
    i = 0
    while i < len(args):
        if args[i] == "--ci-wait-timeout" and i + 1 < len(args):
            try:
                cli_timeout = int(args[i + 1])
            except ValueError:
                cli_timeout = None
            i += 2
            continue
        if args[i] == "--ci-poll-interval" and i + 1 < len(args):
            try:
                cli_interval = int(args[i + 1])
            except ValueError:
                cli_interval = None
            i += 2
            continue
        i += 1

    timeout = (
        cli_timeout
        if cli_timeout is not None
        else _env_int("OPENCODE_CI_WAIT_TIMEOUT", CI_WAIT_TIMEOUT)
    )
    interval = (
        cli_interval
        if cli_interval is not None
        else _env_int("OPENCODE_CI_POLL_INTERVAL", CI_POLL_INTERVAL)
    )
    return CiPollConfig(wait_timeout=timeout, poll_interval=interval)


def parse_remote_url(url: str) -> tuple[str, str, str]:
    """Parse git remote URL into (host, org, repo).

    Supports both HTTPS and SSH formats:
        https://github.com/org/repo.git   -> (github.com, org, repo)
        git@github.com:org/repo.git        -> (github.com, org, repo)
    """
    ssh_match = re.match(r"git@([^:]+):([^/]+)/(.+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2), ssh_match.group(3)
    https_match = re.match(r"https?://([^/]+)/([^/]+)/(.+?)(?:\.git)?$", url)
    if https_match:
        return https_match.group(1), https_match.group(2), https_match.group(3)
    raise ValueError(f"Cannot parse remote URL: {url}")


def get_memory_file_path() -> Path:
    """Derive memory file path from ``git remote get-url origin``."""
    rc, out, err = run_cmd(["git", "remote", "get-url", "origin"])
    if rc != 0:
        raise RuntimeError(f"Cannot get git remote URL: {err.strip()}")
    host, org, repo = parse_remote_url(out.strip())
    return MEMORY_DIR / host / org / f"{repo}.md"


@functools.cache
def get_repo_full_name() -> str:
    """Return ``org/repo`` from git remote (cached, one call per run).

    Used for GitHub Actions API URL: ``repos/{org}/{repo}/actions/runs``.
    Cached via ``functools.cache`` (one git call per process); tests reset
    via ``get_repo_full_name.cache_clear()``.
    """
    rc, out, err = run_cmd(["git", "remote", "get-url", "origin"])
    if rc != 0:
        raise RuntimeError(f"Cannot get git remote URL: {err.strip()}")
    _host, org, repo = parse_remote_url(out.strip())
    return f"{org}/{repo}"


def extract_json_field(json_str: str, field: str) -> str | None:
    """Extract a string field value from JSON (simple regex, no json import)."""
    match = re.search(rf'"{field}"\s*:\s*"([^"]*)"', json_str)
    return match.group(1) if match else None


def check_gh_auth() -> str | None:
    """Check if gh CLI is authenticated. Returns error message or None."""
    rc, _, err = run_cmd(["gh", "auth", "status"])
    if rc != 0:
        return f"gh CLI не авторизован: {err.strip()}"
    return None


def check_issue(pr_number: int) -> PhaseResult:
    """Phase 1: ISSUE — issue exists and linked via Closes/Fixes #N."""
    rc, out, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "body", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return PhaseResult(PhaseStatus.NOT_DONE, f"PR #{pr_number} не существует")

    matches = CLOSURE_RE.findall(out)
    if not matches:
        return PhaseResult(PhaseStatus.NOT_DONE, "Closes/Fixes #N не найден в body")

    issue_numbers = list({int(m) for m in matches})
    if len(issue_numbers) > 1:
        return PhaseResult(
            PhaseStatus.AMBIGUOUS,
            f"несколько issue в body: {', '.join(f'#{n}' for n in issue_numbers)}",
        )

    issue_num = issue_numbers[0]
    rc2, _, err2 = run_cmd(["gh", "issue", "view", str(issue_num), "--repo", get_repo_full_name()])
    if rc2 != 0:
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            f"issue #{issue_num} не существует: {err2.strip()}",
        )

    return PhaseResult(PhaseStatus.DONE, f"#{issue_num} связан через Closes #{issue_num}")


def check_implement(pr_number: int) -> PhaseResult:
    """Phase 2: IMPLEMENT — PR exists + handoff file in diff."""
    rc, out, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "files", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return PhaseResult(PhaseStatus.NOT_DONE, f"PR #{pr_number} не существует")

    files = re.findall(r'"path"\s*:\s*"([^"]+)"', out)
    pattern = f"docs/handoff/pr-{pr_number}-"
    handoff_files = [f for f in files if pattern in f]
    if not handoff_files:
        return PhaseResult(PhaseStatus.NOT_DONE, f"handoff {pattern}*.md не найден в diff")

    return PhaseResult(PhaseStatus.DONE, f"handoff: {Path(handoff_files[0]).name}")


def check_docs(pr_number: int) -> PhaseResult:
    """Phase 3: DOCS — handoff valid (4 sections) + mandatory ADR + docs-reviewer marker.

    Deterministic checks:
    1. Handoff file `docs/handoff/pr-N-*.md` exists.
    2. 4 sections present in handoff content.
    3. ADR file `docs/decisions/*-pr-N-*.md` exists.
    4. PR comment with heading `## Docs Review Summary` from docs-reviewer (proves it ran).

    Without the docs-reviewer comment, DOCS is NOT_DONE — subagent may have written
    handoff+ADR without docs-reviewer actually validating them. Symmetric to
    ``check_review`` which looks for ``## Code Review Summary`` in PR comments.
    """
    handoff_files = sorted(HANDOFF_DIR.glob(f"pr-{pr_number}-*.md"))
    if not handoff_files:
        return PhaseResult(PhaseStatus.NOT_DONE, f"handoff pr-{pr_number}-*.md не найден")

    content = handoff_files[0].read_text()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    if missing:
        return PhaseResult(PhaseStatus.NOT_DONE, f"отсутствуют секции: {', '.join(missing)}")

    adr_result = check_adr(pr_number)
    if adr_result.status != PhaseStatus.DONE:
        return adr_result

    return _check_docs_reviewer_comment(pr_number)


def _check_docs_reviewer_comment(pr_number: int) -> PhaseResult:
    """Phase 3 part: PR comment with 'Docs Review' heading proves docs-reviewer ran."""
    rc, out, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "comments", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return PhaseResult(PhaseStatus.AMBIGUOUS, "не удалось получить комментарии PR")

    comment_bodies = _extract_comment_bodies(out)
    for body in comment_bodies:
        if DOCS_REVIEW_RE.search(body):
            return PhaseResult(PhaseStatus.DONE, "handoff валиден, ADR, docs-review отработал")

    return PhaseResult(
        PhaseStatus.NOT_DONE,
        "docs-reviewer не запущен — запусти @docs-reviewer (pre-merge)",
    )


def check_adr(pr_number: int) -> PhaseResult:
    """Phase 3 part: ADR is mandatory for every PR. Find by PR# in filename."""
    pattern = f"*-pr-{pr_number}-*.md"
    adr_files = sorted(ADR_DIR.glob(pattern)) if ADR_DIR.exists() else []
    if adr_files:
        return PhaseResult(PhaseStatus.DONE, f"ADR: {adr_files[0].name}")
    return PhaseResult(
        PhaseStatus.NOT_DONE,
        f"ADR *-pr-{pr_number}-*.md не найден. "
        f"Создай через bash config/scripts/scaffold-handoff.sh {pr_number} <slug>",
    )


def check_ci(pr_number: int) -> PhaseResult:
    """Phase 4: CI — latest CI run on PR branch completed & success.

    Uses Actions API (read-only, ``Actions: read`` scope). Polls until
    ``status == completed`` or ``CI_WAIT_TIMEOUT`` elapsed. One tool call →
    final status (DONE on green, NOT_DONE on failure, AMBIGUOUS on
    timeout / API error).

    Edge cases (no polling):
    - API error (rc != 0, e.g. 403) → сразу AMBIGUOUS (retries won't help).
    - no runs (jq null) → short retry ``CI_NO_RUNS_RETRY`` times with
      ``CI_NO_RUNS_INTERVAL`` (CI may not be registered right after push),
      then AMBIGUOUS.
    - conclusion != success → сразу NOT_DONE (fix the failure, don't wait).
    - status in (in_progress, queued, ...) → polling loop with
      ``sleep(CI_POLL_INTERVAL)`` + re-query until completed or timeout.
    """
    head_branch, branch_error = _get_pr_head_branch(pr_number)
    if branch_error is not None or head_branch is None:
        return PhaseResult(PhaseStatus.AMBIGUOUS, branch_error or "head_branch is None")

    config = _load_ci_config()
    return _run_ci_loop(head_branch, config)


def _run_ci_loop(head_branch: str, config: CiPollConfig) -> PhaseResult:
    """Initial CI query + edge-case dispatch + delegate to poll/no-runs helpers."""
    kind, runs_str, err = _query_ci_run(head_branch)
    if kind == "error":
        return PhaseResult(PhaseStatus.AMBIGUOUS, err)
    if kind == "no_runs":
        return _retry_no_runs(head_branch, config)
    status = _extract_json_field_loose(runs_str, "status")
    if status is None:
        return PhaseResult(PhaseStatus.AMBIGUOUS, "не удалось распарсить status CI run")
    if status == "completed":
        conclusion = _extract_json_field_loose(runs_str, "conclusion")
        return _classify_ci_status(status, conclusion)
    return _poll_until_done(head_branch, config, runs_str, status)


def _retry_no_runs(head_branch: str, config: CiPollConfig) -> PhaseResult:
    """Retry CI query when no run registered yet (CI may lag after push).

    Up to ``CI_NO_RUNS_RETRY`` total attempts (initial + retries), sleeping
    ``CI_NO_RUNS_INTERVAL`` between attempts. On success → classify/poll;
    on API error → AMBIGUOUS; exhausted → AMBIGUOUS.
    """
    for attempt in range(CI_NO_RUNS_RETRY):
        if attempt > 0:
            time.sleep(CI_NO_RUNS_INTERVAL)
        kind, runs_str, err = _query_ci_run(head_branch)
        if kind == "error":
            return PhaseResult(PhaseStatus.AMBIGUOUS, err)
        if kind == "run":
            status = _extract_json_field_loose(runs_str, "status")
            if status is None:
                return PhaseResult(PhaseStatus.AMBIGUOUS, "не удалось распарсить status CI run")
            if status == "completed":
                conclusion = _extract_json_field_loose(runs_str, "conclusion")
                return _classify_ci_status(status, conclusion)
            return _poll_until_done(head_branch, config, runs_str, status)
    return PhaseResult(
        PhaseStatus.AMBIGUOUS,
        f"нет CI run на ветке {head_branch} — возможна проблема триггера",
    )


def _poll_until_done(
    head_branch: str, config: CiPollConfig, runs_str: str, last_status: str
) -> PhaseResult:
    """Poll Actions API until status == completed or CI_WAIT_TIMEOUT elapsed.

    ``runs_str``/``last_status`` are the most recent query results (avoids
    re-querying immediately). Sleeps ``CI_POLL_INTERVAL`` between queries.
    On timeout → AMBIGUOUS (CI still running — check manually). On completed
    → classify.
    """
    elapsed = 0
    status = last_status
    runs_str_cur = runs_str
    while status != "completed" and elapsed < config.wait_timeout:
        if elapsed + config.poll_interval > config.wait_timeout:
            break
        time.sleep(config.poll_interval)
        elapsed += config.poll_interval
        kind, runs_str_new, err = _query_ci_run(head_branch)
        if kind == "error":
            return PhaseResult(PhaseStatus.AMBIGUOUS, err)
        if kind == "no_runs":
            return PhaseResult(
                PhaseStatus.AMBIGUOUS,
                f"нет CI run на ветке {head_branch} — возможна проблема триггера",
            )
        runs_str_cur = runs_str_new
        status_new = _extract_json_field_loose(runs_str_cur, "status")
        if status_new is None:
            return PhaseResult(PhaseStatus.AMBIGUOUS, "не удалось распарсить status CI run")
        status = status_new
    if status == "completed":
        conclusion = _extract_json_field_loose(runs_str_cur, "conclusion")
        return _classify_ci_status(status, conclusion)
    return PhaseResult(
        PhaseStatus.AMBIGUOUS,
        f"CI ещё идёт после {config.wait_timeout}s — проверь вручную: "
        f"gh run view --branch {head_branch}",
    )


def _get_pr_head_branch(pr_number: int) -> tuple[str | None, str | None]:
    """Return (head_branch, None) or (None, error_message)."""
    rc, out, err = run_cmd(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "headRefName",
            "--repo",
            get_repo_full_name(),
        ]
    )
    if rc != 0:
        return None, f"не удалось получить ветку PR: {err.strip()}"
    head_branch = extract_json_field(out, "headRefName")
    if not head_branch:
        return None, "не удалось распарсить headRefName PR"
    return head_branch, None


def _query_ci_run(head_branch: str) -> tuple[str, str, str]:
    """Query Actions API for latest CI run on ``head_branch``.

    Return ``(kind, json_str, error)`` where ``kind`` is one of:
    - ``"error"`` — API call failed (rc != 0, e.g. 403), ``error`` set.
    - ``"no_runs"`` — jq returned null/empty (no CI run registered yet).
    - ``"run"`` — JSON with status/conclusion, ``json_str`` set.
    """
    jq_filter = (
        f'[.workflow_runs[] | select(.head_branch == "{head_branch}") '
        f'| select(.name == "CI")] | .[0]'
    )
    rc, out, err = run_cmd(
        [
            "gh",
            "api",
            f"repos/{get_repo_full_name()}/actions/runs",
            "--jq",
            jq_filter,
        ]
    )
    if rc != 0:
        return "error", "", f"Actions API error: {err.strip()}"
    runs_str = out.strip()
    if not runs_str or runs_str == "null":
        return "no_runs", "", ""
    return "run", runs_str, ""


def _classify_ci_status(status: str, conclusion: str | None) -> PhaseResult:
    """Map CI status+conclusion to PhaseResult."""
    if status != "completed":
        return PhaseResult(PhaseStatus.AMBIGUOUS, f"CI {status} — wait")
    if conclusion is None:
        return PhaseResult(
            PhaseStatus.AMBIGUOUS,
            "CI completed but conclusion missing",
        )
    if conclusion != "success":
        return PhaseResult(PhaseStatus.NOT_DONE, f"CI {conclusion} — fix needed")
    return PhaseResult(PhaseStatus.DONE, "CI green")


def _extract_json_field_loose(json_str: str, field: str) -> str | None:
    """Extract a JSON string field handling null values (unlike extract_json_field).

    ``extract_json_field`` uses ``"([^"]*)"`` which never matches ``null``.
    This helper accepts both ``"value"`` and ``null`` (returns None for null).
    """
    match = re.search(rf'"{field}"\s*:\s*"(?P<v>[^"]*)"', json_str)
    if match:
        return match.group("v")
    null_match = re.search(rf'"{field}"\s*:\s*null', json_str)
    if null_match:
        return None
    return None


def _extract_comment_bodies(json_str: str) -> list[str]:
    """Extract 'body' fields from gh pr view --json comments output.

    Handles JSON string escaping (\\n, \\", \\\\).
    """
    bodies = []
    for match in re.finditer(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str):
        raw = match.group(1)
        body = raw.encode().decode("unicode_escape")
        bodies.append(body)
    return bodies


def check_review(pr_number: int) -> PhaseResult:
    """Phase 5: REVIEW — APPROVE found in PR comments from code reviewer.

    Looks for '## Code Review Summary' heading (NOT '## Docs Review Summary')
    with '### Verdict: APPROVE'. Only the latest reviewer comment counts —
    if reviewer changed from APPROVE to REQUEST_CHANGES, NOT_DONE.
    """
    rc, out, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "comments", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return PhaseResult(PhaseStatus.NOT_DONE, "не удалось получить комментарии PR")

    comment_bodies = _extract_comment_bodies(out)
    if not comment_bodies:
        return PhaseResult(PhaseStatus.NOT_DONE, "нет комментариев PR")

    reviewer_verdict = None
    for body in comment_bodies:
        if REVIEW_VERDICT_RE.search(body):
            match = REVIEW_VERDICT_RE.search(body)
            reviewer_verdict = match.group(1).upper() if match else None

    if reviewer_verdict is None:
        return PhaseResult(PhaseStatus.NOT_DONE, "Code Review Summary не найден в комментариях")

    if reviewer_verdict == "APPROVE":
        return PhaseResult(PhaseStatus.DONE, "APPROVE найден в Code Review Summary")

    return PhaseResult(PhaseStatus.NOT_DONE, f"последний verdict reviewer'а: {reviewer_verdict}")


def check_merge(pr_number: int) -> PhaseResult:
    """Phase 6: MERGE — PR state is MERGED."""
    rc, out, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "state", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return PhaseResult(PhaseStatus.NOT_DONE, f"PR #{pr_number} не существует")

    state = extract_json_field(out, "state")
    if state is None:
        return PhaseResult(PhaseStatus.AMBIGUOUS, "не удалось распарсить state PR")

    if state == "MERGED":
        return PhaseResult(PhaseStatus.DONE, "merged")

    return PhaseResult(PhaseStatus.NOT_DONE, f"state={state}")


def check_memory(pr_number: int) -> PhaseResult:
    """Phase 7: MEMORY — PR#N distilled into memory file."""
    try:
        memory_file = get_memory_file_path()
    except (RuntimeError, ValueError) as exc:
        return PhaseResult(PhaseStatus.NOT_DONE, str(exc))

    if not memory_file.exists():
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            f"memory file не существует: {memory_file.name}",
        )

    content = memory_file.read_text()
    pattern = f"PR#{pr_number}"
    if pattern in content:
        return PhaseResult(PhaseStatus.DONE, f"{pattern} в {memory_file.name}")

    return PhaseResult(
        PhaseStatus.NOT_DONE,
        f"{pattern} не найден в {memory_file.name}",
    )


def get_pr_title(pr_number: int) -> str:
    """Get PR title via gh CLI."""
    rc, out, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "title", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return f"PR #{pr_number}"
    title = extract_json_field(out, "title")
    return title if title else f"PR #{pr_number}"


NEXT_ACTIONS: dict[str, str] = {
    "ISSUE": "создать issue и связать через Closes #N в body PR",
    "IMPLEMENT": "добавить handoff docs/handoff/pr-N-slug.md в diff",
    "DOCS": "запустить docs-reviewer (режим pre-merge)",
    "CI": "проверь статус CI вручную (gh run view)",
    "REVIEW": "запустить reviewer (task subagent_type=reviewer)",
    "MERGE": "смержить PR (gh pr merge N --squash --delete-branch)",
    "MEMORY": "запустить memory-syncer",
}

REVIEW_NEXT_REQUEST_CHANGES = (
    "запусти fix subagent (general) с prompt 'fix reviewer comments: <list>', "
    "commit, push → re-loop (pipeline_status проверит CI автоматически)"
)
REVIEW_NEXT_NEEDS_DISCUSSION = "уточни вопросы с автором PR (verdict: NEEDS_DISCUSSION)"
REVIEW_NEXT_DEFAULT = NEXT_ACTIONS["REVIEW"]

STATUS_ICONS: dict[PhaseStatus, str] = {
    PhaseStatus.DONE: "✅",
    PhaseStatus.NOT_DONE: "❌",
    PhaseStatus.AMBIGUOUS: "⚠️",
}


def get_next_action(phase_name: str, pr_number: int) -> str:
    """Get NEXT action description for a not-done phase."""
    action = NEXT_ACTIONS.get(phase_name, "уточнить статус")
    return action.replace("N", str(pr_number))


def get_next_action_review(result: PhaseResult) -> str:
    """REVIEW-фаза: NEXT зависит от вердикта reviewer'а в result.detail."""
    detail = result.detail.upper()
    if "REQUEST_CHANGES" in detail:
        return REVIEW_NEXT_REQUEST_CHANGES
    if "NEEDS_DISCUSSION" in detail:
        return REVIEW_NEXT_NEEDS_DISCUSSION
    return REVIEW_NEXT_DEFAULT


def run_all_checks(pr_number: int) -> list[PhaseResult]:
    """Run all 7 phase checks, return results in order."""
    return [
        check_issue(pr_number),
        check_implement(pr_number),
        check_docs(pr_number),
        check_ci(pr_number),
        check_review(pr_number),
        check_merge(pr_number),
        check_memory(pr_number),
    ]


def find_current_phase(results: list[PhaseResult]) -> int | None:
    """Return index of first not-done phase, or None if all done."""
    for i, result in enumerate(results):
        if result.status != PhaseStatus.DONE:
            return i
    return None


def format_single_pr(pr_number: int, results: list[PhaseResult]) -> str:
    """Format detailed output for a single PR."""
    title = get_pr_title(pr_number)
    lines = [f"PR #{pr_number}: {title}", ""]

    for i, (name, result) in enumerate(zip(PHASE_NAMES, results, strict=True)):
        icon = STATUS_ICONS[result.status]
        lines.append(f"{icon} {i + 1}. {name:<12} {result.detail}")

    lines.append("")

    current = find_current_phase(results)
    if current is None:
        lines.append("Status: COMPLETE")
    else:
        result = results[current]
        if result.status == PhaseStatus.AMBIGUOUS:
            lines.append(f"AMBIGUOUS: {result.detail}")
            lines.append("NEXT: уточните статус вручную")
        else:
            if PHASE_NAMES[current] == "REVIEW":
                action = get_next_action_review(result)
            else:
                action = get_next_action(PHASE_NAMES[current], pr_number)
            lines.append(f"NEXT: {action}")

    return "\n".join(lines)


def list_open_pr_numbers() -> list[int]:
    """List numbers of all open PRs."""
    rc, out, _ = run_cmd(
        ["gh", "pr", "list", "--state", "open", "--json", "number", "--repo", get_repo_full_name()]
    )
    if rc != 0:
        return []
    numbers = re.findall(r'"number"\s*:\s*(\d+)', out)
    return sorted(int(n) for n in numbers)


def format_pr_row(pr_number: int) -> str:
    """Format a single row for the open-PRs table."""
    results = run_all_checks(pr_number)
    title = get_pr_title(pr_number)
    icon_str = "".join(STATUS_ICONS[r.status] for r in results)

    current = find_current_phase(results)
    if current is None:
        next_action = "COMPLETE"
    elif PHASE_NAMES[current] == "REVIEW":
        next_action = get_next_action_review(results[current])
    else:
        next_action = get_next_action(PHASE_NAMES[current], pr_number)

    short_title = title[:40] + "..." if len(title) > 40 else title
    return f"PR#{pr_number:<5} {short_title:<43} {icon_str}  NEXT: {next_action}"


def format_table(pr_numbers: list[int]) -> str:
    """Format table of all open PRs."""
    if not pr_numbers:
        return "Нет открытых PR"
    rows = [format_pr_row(n) for n in pr_numbers]
    return "\n".join(rows)


def pr_exists(pr_number: int) -> bool:
    """Check if PR exists via gh CLI."""
    rc, _, _ = run_cmd(
        ["gh", "pr", "view", str(pr_number), "--json", "number", "--repo", get_repo_full_name()]
    )
    return rc == 0


def main() -> None:
    """Entry point: parse args and dispatch to single-PR or table mode."""
    auth_error = check_gh_auth()
    if auth_error:
        print(auth_error, file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) > 1:
        try:
            pr_number = int(sys.argv[1])
        except ValueError:
            print(f"Некорректный номер PR: {sys.argv[1]}", file=sys.stderr)
            sys.exit(1)

        if not pr_exists(pr_number):
            print(f"PR #{pr_number} не существует", file=sys.stderr)
            sys.exit(1)

        results = run_all_checks(pr_number)
        print(format_single_pr(pr_number, results))
    else:
        pr_numbers = list_open_pr_numbers()
        print(format_table(pr_numbers))


if __name__ == "__main__":
    main()
