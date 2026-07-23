#!/usr/bin/env python3
"""Spec-status oracle: determine current phase of a project spec.

Reads facts from ``docs/spec/*.md`` files (one file per phase) to
deterministically derive the current spec phase — no state file, like
``git status`` for the spec pipeline. Repo-aware via
``_resolve_repo_root()`` (cwd-aware, ADR-010) and ``get_repo_full_name()``
via ``git remote get-url origin`` + ``@functools.cache`` (ADR-007).
``gh issue view --repo <org/repo>`` in Phase 8 (ADR-023).

Usage:
    python3 config/scripts/spec-status.py              # current phase
    python3 config/scripts/spec-status.py --validate   # all phases detail

Structure of ``docs/spec/``:
    meta.md            frontmatter: project, type, created, phase, confirmed,
                       executed, no_db
    context.md         Phase 1: project description
    stack.md           Phase 2: stack (default + choices)
    modules.md         Phase 3: modules + structure tree
    db-schema.md       Phase 4 (optional — absent if no_db: true)
    infra.md           Phase 5: infra
    roadmap.md         Phase 6: roadmap with #N issue numbers

Nine phases:
    0. DETECT       — docs/spec/meta.md exists + frontmatter project: key
    1. PROJECT_TYPE — type/project in frontmatter + context.md filled
    2. STACK        — stack.md filled + mandatory items per project type
    3. MODULES      — modules.md filled + >=1 bullet item
    4. DB_SCHEMA    — no_db: true OR db-schema.md filled
    5. INFRA        — infra.md filled (>=3 chars)
    6. ROADMAP      — roadmap.md filled + >=1 bullet item
    7. CONFIRM      — confirmed: true in meta.md frontmatter
    8. EXECUTE      — executed: true + roadmap #N issues exist (gh view)
"""

from __future__ import annotations

import functools
import re
import subprocess
import sys
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
SPEC_DIR = REPO_ROOT / "docs" / "spec"
META_FILE = SPEC_DIR / "meta.md"
PHASE_FILES: dict[int, str] = {
    1: "context.md",
    2: "stack.md",
    3: "modules.md",
    4: "db-schema.md",
    5: "infra.md",
    6: "roadmap.md",
}

VALID_TYPES = {"backend", "fullstack", "mcp-server", "cli", "bot", "worker"}

STACK_REQUIRED: dict[str, list[str]] = {
    "backend": ["fastapi", "tortoise", "uv", "pytest", "ruff", "mypy"],
    "fullstack": ["fastapi", "tortoise", "react", "vite", "biome", "uv"],
    "mcp-server": ["fastapi", "mcp", "patchright", "uv"],
    "cli": ["typer", "uv", "hatchling"],
    "bot": ["aiogram", "fastapi", "uv"],
    "worker": ["prefect", "uv"],
}

PHASE_NAMES = [
    "DETECT",
    "PROJECT_TYPE",
    "STACK",
    "MODULES",
    "DB_SCHEMA",
    "INFRA",
    "ROADMAP",
    "CONFIRM",
    "EXECUTE",
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
KV_RE = re.compile(r"^(\w+):\s*(.*?)$", re.MULTILINE)


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


@functools.cache
def get_repo_full_name() -> str:
    """Return ``org/repo`` from git remote (cached, one call per run).

    Used for ``gh issue view --repo <org/repo>`` in Phase 8. Cached via
    ``functools.cache`` (one git call per process); tests reset via
    ``get_repo_full_name.cache_clear()``.
    """
    rc, out, err = run_cmd(["git", "remote", "get-url", "origin"])
    if rc != 0:
        raise RuntimeError(f"Cannot get git remote URL: {err.strip()}")
    _host, org, repo = parse_remote_url(out.strip())
    return f"{org}/{repo}"


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse simple key: value frontmatter (no nested structures)."""
    match = FRONTMATTER_RE.search(content)
    if not match:
        return {}
    fm_text = match.group(1)
    return dict(KV_RE.findall(fm_text))


def read_meta() -> tuple[str, dict[str, str]]:
    """Read docs/spec/meta.md content + parsed frontmatter.

    Returns ``("", {})`` if meta.md is missing.
    """
    if not META_FILE.exists():
        return "", {}
    content = META_FILE.read_text()
    return content, parse_frontmatter(content)


def file_filled(path: Path) -> bool:
    """Return True if path exists and its text content (stripped) is non-empty."""
    return path.exists() and bool(path.read_text().strip())


def has_bullet_items(path: Path) -> bool:
    """Return True if file contains >=1 line starting with ``-`` or ``*``."""
    if not path.exists():
        return False
    return any(line.lstrip().startswith(("-", "*")) for line in path.read_text().splitlines())


def check_detect() -> PhaseResult:
    """Phase 0: DETECT — meta.md exists + frontmatter + project: key."""
    if not META_FILE.exists():
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/meta.md не найден — инициализируй spec")
    _content, fm = read_meta()
    if not fm:
        return PhaseResult(PhaseStatus.NOT_DONE, "frontmatter пустой — инициализируй spec")
    if "project" not in fm:
        return PhaseResult(PhaseStatus.NOT_DONE, "frontmatter: ключ project: отсутствует")
    return PhaseResult(PhaseStatus.DONE, "spec инициализирован")


def check_project_type() -> PhaseResult:
    """Phase 1: PROJECT_TYPE — type/project in frontmatter + context.md filled."""
    _content, fm = read_meta()
    if not fm:
        return PhaseResult(PhaseStatus.NOT_DONE, "frontmatter пустой")
    ptype = fm.get("type", "").strip()
    project = fm.get("project", "").strip()
    if not ptype or not project:
        return PhaseResult(PhaseStatus.NOT_DONE, "type: или project: пустой в frontmatter")
    if ptype not in VALID_TYPES:
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            f"type={ptype} невалиден (допустимо: {', '.join(sorted(VALID_TYPES))})",
        )
    context_file = SPEC_DIR / PHASE_FILES[1]
    if not file_filled(context_file):
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/context.md не заполнен")
    return PhaseResult(PhaseStatus.DONE, f"{ptype} выбран, project={project}")


def check_stack() -> PhaseResult:
    """Phase 2: STACK — stack.md filled + mandatory items per project type."""
    _content, fm = read_meta()
    ptype = fm.get("type", "").strip()
    if ptype not in VALID_TYPES:
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            f"type={ptype or '—'} невалиден, STACK нельзя проверить",
        )
    stack_file = SPEC_DIR / PHASE_FILES[2]
    if not file_filled(stack_file):
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/stack.md не заполнен")
    required = STACK_REQUIRED[ptype]
    stack_body = stack_file.read_text()
    stack_lower = stack_body.lower()
    missing = [item for item in required if item not in stack_lower]
    if missing:
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            f"не хватает mandatory items: {', '.join(missing)}",
        )
    return PhaseResult(PhaseStatus.DONE, f"все {len(required)} mandatory items присутствуют")


def check_modules() -> PhaseResult:
    """Phase 3: MODULES — modules.md filled + >=1 bullet item."""
    modules_file = SPEC_DIR / PHASE_FILES[3]
    if not file_filled(modules_file):
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/modules.md не заполнен")
    if not has_bullet_items(modules_file):
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            "docs/spec/modules.md без пунктов (нужен '-' или '*')",
        )
    bullets = [
        line
        for line in modules_file.read_text().splitlines()
        if line.lstrip().startswith(("-", "*"))
    ]
    return PhaseResult(PhaseStatus.DONE, f"{len(bullets)} модул(ей)")


def check_db_schema() -> PhaseResult:
    """Phase 4: DB_SCHEMA — no_db: true OR db-schema.md filled."""
    _content, fm = read_meta()
    if fm.get("no_db", "").strip().lower() in {"true", '"true"'}:
        return PhaseResult(PhaseStatus.DONE, "no_db: true (DB не нужна)")
    db_file = SPEC_DIR / PHASE_FILES[4]
    if not file_filled(db_file):
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            "docs/spec/db-schema.md не заполнен (или no_db: true в frontmatter)",
        )
    return PhaseResult(PhaseStatus.DONE, "docs/spec/db-schema.md заполнен")


def check_infra() -> PhaseResult:
    """Phase 5: INFRA — infra.md filled (>=3 chars)."""
    infra_file = SPEC_DIR / PHASE_FILES[5]
    if not file_filled(infra_file):
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/infra.md не заполнен")
    body = infra_file.read_text().strip()
    if len(body) < 3:
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/infra.md пустой (<3 символов)")
    return PhaseResult(PhaseStatus.DONE, "docs/spec/infra.md заполнен")


def check_roadmap() -> PhaseResult:
    """Phase 6: ROADMAP — roadmap.md filled + >=1 bullet item."""
    roadmap_file = SPEC_DIR / PHASE_FILES[6]
    if not file_filled(roadmap_file):
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/roadmap.md не заполнен")
    if not has_bullet_items(roadmap_file):
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            "docs/spec/roadmap.md без пунктов (нужен '-' или '*')",
        )
    bullets = [
        line
        for line in roadmap_file.read_text().splitlines()
        if line.lstrip().startswith(("-", "*"))
    ]
    return PhaseResult(PhaseStatus.DONE, f"{len(bullets)} пунктов в roadmap")


def check_confirm() -> PhaseResult:
    """Phase 7: CONFIRM — confirmed: true in meta.md frontmatter."""
    _content, fm = read_meta()
    val = fm.get("confirmed", "").strip().lower()
    if val not in {"true", '"true"'}:
        return PhaseResult(PhaseStatus.NOT_DONE, "confirmed: true отсутствует в frontmatter")
    return PhaseResult(PhaseStatus.DONE, "spec подтверждён юзером")


def _extract_issue_numbers(content: str) -> list[int]:
    """Extract #N issue references from roadmap.md content."""
    return [int(m) for m in re.findall(r"#(\d+)", content)]


def _check_roadmap_issues(repo: str, issue_nums: list[int]) -> PhaseResult:
    """Phase 8 part: verify each #N issue exists via ``gh issue view --repo``.

    Returns DONE if all issues found, NOT_DONE if any missing.
    """
    missing: list[int] = []
    for num in issue_nums:
        rc, _, _ = run_cmd(["gh", "issue", "view", str(num), "--repo", repo])
        if rc != 0:
            missing.append(num)
    if missing:
        return PhaseResult(
            PhaseStatus.NOT_DONE,
            f"issues не созданы/не найдены: {', '.join(f'#{n}' for n in missing)}",
        )
    return PhaseResult(PhaseStatus.DONE, f"все {len(issue_nums)} issues созданы")


def check_execute() -> PhaseResult:
    """Phase 8: EXECUTE — executed: true + issues created (gh view --repo)."""
    _content, fm = read_meta()
    val = fm.get("executed", "").strip().lower()
    if val not in {"true", '"true"'}:
        return PhaseResult(PhaseStatus.NOT_DONE, "executed: true отсутствует в frontmatter")
    roadmap_file = SPEC_DIR / PHASE_FILES[6]
    if not roadmap_file.exists():
        return PhaseResult(PhaseStatus.NOT_DONE, "docs/spec/roadmap.md не найден для проверки #N")
    issue_nums = _extract_issue_numbers(roadmap_file.read_text())
    if not issue_nums:
        return PhaseResult(PhaseStatus.NOT_DONE, "в roadmap.md нет #N ссылок для проверки")
    try:
        repo = get_repo_full_name()
    except (RuntimeError, ValueError) as exc:
        return PhaseResult(PhaseStatus.AMBIGUOUS, f"git remote error: {exc}")
    return _check_roadmap_issues(repo, issue_nums)


PHASE_CHECKS = [
    check_detect,
    check_project_type,
    check_stack,
    check_modules,
    check_db_schema,
    check_infra,
    check_roadmap,
    check_confirm,
    check_execute,
]

NEXT_ACTIONS: dict[str, str] = {
    "DETECT": "создай docs/spec/meta.md с frontmatter (project, type, created, phase, status)",
    "PROJECT_TYPE": "запроси у юзера тип + имя, заполни meta.md frontmatter + создай context.md",
    "STACK": "создай docs/spec/stack.md (default stack для типа + choices юзера)",
    "MODULES": "запроси модули, создай docs/spec/modules.md (## Модули + ## Структура)",
    "DB_SCHEMA": "создай docs/spec/db-schema.md (или no_db: true в meta.md)",
    "INFRA": "создай docs/spec/infra.md (Docker, Prefect, MCP, Tunnel)",
    "ROADMAP": "создай docs/spec/roadmap.md — N пунктов для будущих issues",
    "CONFIRM": "покажи spec юзеру, поставь confirmed: true в meta.md после подтверждения",
    "EXECUTE": "создай GitHub issues по roadmap, поставь executed: true в meta.md",
}

STATUS_ICONS: dict[PhaseStatus, str] = {
    PhaseStatus.DONE: "✅",
    PhaseStatus.NOT_DONE: "❌",
    PhaseStatus.AMBIGUOUS: "⚠️",
}


def find_current_phase(results: list[PhaseResult]) -> int | None:
    """Return index of first not-done phase, or None if all done."""
    for i, result in enumerate(results):
        if result.status != PhaseStatus.DONE:
            return i
    return None


def run_all_checks() -> list[PhaseResult]:
    """Run all 9 phase checks, return results in order."""
    return [check() for check in PHASE_CHECKS]


def format_output(results: list[PhaseResult], fm: dict[str, str]) -> str:
    """Format output: 9 phase lines + NEXT or COMPLETE."""
    validate = "--validate" in sys.argv[1:]
    project = fm.get("project", "").strip() or "<unnamed>"
    lines: list[str] = [f"Spec: {project}", ""]

    for i, (name, result) in enumerate(zip(PHASE_NAMES, results, strict=True)):
        icon = STATUS_ICONS[result.status]
        if validate or result.status != PhaseStatus.DONE:
            lines.append(f"{icon} {i}. {name:<12} {result.detail}")
        else:
            lines.append(f"{icon} {i}. {name:<12} done")

    lines.append("")

    current = find_current_phase(results)
    if current is None:
        lines.append("Status: COMPLETE")
        return "\n".join(lines)

    result = results[current]
    phase_name = PHASE_NAMES[current]
    if result.status == PhaseStatus.AMBIGUOUS:
        lines.append(f"AMBIGUOUS: {result.detail}")
        lines.append("NEXT: уточните статус вручную")
    else:
        action = NEXT_ACTIONS.get(phase_name, "уточнить статус")
        lines.append(f"NEXT: {action} (Phase {current})")

    return "\n".join(lines)


def main() -> None:
    """Entry point: parse args, run checks, print status."""
    results = run_all_checks()
    _content, fm = read_meta()
    print(format_output(results, fm))


if __name__ == "__main__":
    main()
