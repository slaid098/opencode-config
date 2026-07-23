#!/usr/bin/env python3
"""Check ADR references in markdown files for dangling pointers.

Scans ``.md`` files in the repo for ``ADR-NNN`` references and verifies
that a corresponding ``docs/decisions/NNN-*.md`` file exists. Dangling
references (typos, forward-refs) fail CI — symmetric to
``check-permissions.py`` (ADR-006 pattern).

Self-reference is excluded: if the current file's name starts with
``NNN-``, a reference to ``ADR-NNN`` inside it is OK (an ADR file may
mention its own number).

What is NOT caught: wrong existing refs (``ADR-017`` exists but is
semantically wrong for a given PR) — that requires semantic analysis.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ADR_DIR = REPO_ROOT / "docs" / "decisions"
ADR_REF_RE = re.compile(r"\bADR-(\d{3})\b")

EXCLUDE_DIRS = {"node_modules", ".git", "app_data", ".opencode"}


def _is_excluded(path: Path) -> bool:
    """True if ``path`` is inside an excluded directory (node_modules, .git, ...)."""
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        return True
    parts = rel.parts
    return any(excl in parts for excl in EXCLUDE_DIRS)


def find_md_files() -> list[Path]:
    """Return all ``.md`` files under REPO_ROOT, excluding node_modules/.git/etc."""
    results: list[Path] = []
    for md_file in REPO_ROOT.rglob("*.md"):
        if _is_excluded(md_file):
            continue
        results.append(md_file)
    return sorted(results)


def find_adr_refs(md_file: Path) -> list[tuple[int, str]]:
    """Return ``[(line_number, adr_number), ...]`` for every ``ADR-NNN`` in ``md_file``."""
    refs: list[tuple[int, str]] = []
    text = md_file.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in ADR_REF_RE.finditer(line):
            refs.append((line_no, match.group(1)))
    return refs


def is_self_reference(md_file: Path, adr_number: str) -> bool:
    """True if ``md_file``'s name starts with ``NNN-`` where NNN == adr_number."""
    return md_file.name.startswith(f"{adr_number}-")


def adr_exists(adr_number: str) -> bool:
    """True if ``docs/decisions/NNN-*.md`` exists for the given number."""
    if not ADR_DIR.exists():
        return False
    return any(ADR_DIR.glob(f"{adr_number}-*.md"))


def main() -> None:
    all_violations: list[str] = []
    for md_file in find_md_files():
        refs = find_adr_refs(md_file)
        for ref_line, ref_number in refs:
            if is_self_reference(md_file, ref_number):
                continue
            if not adr_exists(ref_number):
                all_violations.append(
                    f"  {md_file.relative_to(REPO_ROOT)}:{ref_line}: "
                    f"ADR-{ref_number} reference, but "
                    f"docs/decisions/{ref_number}-*.md does not exist"
                )

    if not all_violations:
        print("OK: No dangling ADR references.")
        sys.exit(0)

    print("FAIL: Dangling ADR references:\n")
    for v in all_violations:
        print(v)
    print(f"\nTotal: {len(all_violations)} violation(s)")
    sys.exit(1)


if __name__ == "__main__":
    main()
