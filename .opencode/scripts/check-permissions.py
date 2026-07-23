#!/usr/bin/env python3
"""Check agent permission configs for dangerous allow rules."""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = REPO_ROOT / "config" / "agents"
OPENCODE_JSON = REPO_ROOT / "config" / "opencode.json"

DANGEROUS_PATTERNS = [
    (r"^gh api\*?$", "broad — allows gh api -X DELETE/PUT/POST"),
    (r"^gh api \*$", "broad — allows gh api -X DELETE/PUT/POST"),
    (r"^gh api -X (DELETE|PUT|POST|PATCH)\*?$", "destructive HTTP method"),
    (r"^gh api --method (DELETE|PUT|POST|PATCH)\*?$", "destructive HTTP method"),
    (
        r"^gh pr checks\*?$",
        "uses GraphQL statusCheckRollup → Checks API → 403 on fine-grained PAT "
        "(scope 'Checks: read' does not exist). Use 'gh run list'/'gh run view' or "
        "'gh api repos/.../actions/runs' (actions=read scope). See ADR-005.",
    ),
    (
        r"^gh pr view \*--json statusCheckRollup\*?$",
        "GraphQL statusCheckRollup → Checks API → 403 on fine-grained PAT. "
        "Use 'gh pr view --json headRefName,body,title' (metadata only) or "
        "'gh run list' for CI status. See ADR-005.",
    ),
    (
        r"^gh pr merge\*?$",
        "merge is done by main agent via run-pipeline, not subagents. "
        "Use 'gh pr merge' from primary build/plan agent only (global "
        "opencode.json:195 has 'gh pr merge*: allow'). Per-agent 'gh pr "
        "merge*: deny' is the defense (see ADR-016). See ADR-006 for "
        "DANGEROUS_PATTERNS mechanism.",
        "agent",
    ),
    (
        r"^python3? .*pipeline-status\.py",
        "use pipeline_status tool, not bash. See ADR-019",
        "agent",
    ),
    (
        r"^python .*pipeline-status\.py",
        "use pipeline_status tool, not bash. See ADR-019",
        "agent",
    ),
    (
        r"^python3? .*spec-status\.py",
        "use spec_status tool, not bash. See ADR-NNN",
        "agent",
    ),
    (
        r"^python .*spec-status\.py",
        "use spec_status tool, not bash. See ADR-NNN",
        "agent",
    ),
    (r"^gh repo\*?$", "broad — allows gh repo delete"),
    (r"^gh repo \*$", "broad — allows gh repo delete"),
    (r"^gh repo (delete|edit|rename|archive|unarchive|sync)\*?$", "destructive repo operation"),
    (r"^git -C \*$", "broad — allows any git command in any dir"),
    (r"^git reset \*", "destroys uncommitted changes"),
    (r"^git clean \*", "deletes untracked files"),
    (r"^git push --force\*", "rewrites remote history"),
    (r"^git push --delete\*", "deletes remote branches"),
    (r"^git push -f\*", "rewrites remote history"),
    (r"^git push origin --delete\*", "deletes remote branches"),
    (r"^rm -rf", "recursive force delete"),
    (r"^rm -f /", "force delete system files"),
    (r"^rm /", "delete system files"),
    (r"^rmdir \*", "delete directories"),
    (r"^shred \*", "secure delete"),
    (r"^sudo\*?$", "privilege escalation"),
    (r"^sudo \*", "privilege escalation"),
    (r"^chmod \*", "change permissions"),
    (r"^chown \*", "change ownership"),
    (r"^mkfs\*", "format filesystem"),
    (r"^dd \*", "raw disk write"),
    (r"^fdisk\*", "modify partitions"),
    (r"^shutdown\*", "shutdown system"),
    (r"^reboot\*", "reboot system"),
    (r"^halt\*", "halt system"),
    (r"^poweroff\*", "power off system"),
    (r"^docker system prune\*", "prune everything"),
    (r"^docker rm \*", "remove containers"),
    (r"^docker rmi \*", "remove images"),
    (r"^docker volume rm \*", "remove volumes"),
    (r"^docker network rm \*", "remove networks"),
    (r"^ssh \* mkfs\*", "format remote disk"),
    (r"^ssh \* dd \*", "raw disk write on remote"),
    (r"^ssh \* fdisk\*", "modify partitions on remote"),
    (r"^ssh \* reboot\*", "reboot remote"),
    (r"^ssh \* shutdown\*", "shutdown remote"),
    (r"^ssh \* halt\*", "halt remote"),
    (r"^ssh \* poweroff\*", "power off remote"),
    (r"^ssh \* rm \*", "delete files on remote"),
    (r"^ssh \* chmod\*", "change permissions on remote"),
    (r"^ssh \* chown\*", "change ownership on remote"),
    (r"^kubectl delete \*", "delete k8s resources"),
    (r"^kubectl scale \*", "scale k8s resources"),
    (r"^kill -9 \*", "force kill processes"),
    (r"^killall\*", "kill processes by name"),
    (r"^pkill\*", "kill processes by pattern"),
    (r"^npm install\*", "install arbitrary packages"),
    (r"^npm i \*", "install arbitrary packages"),
    (r"^npm add\*", "install arbitrary packages"),
    (r"^pip install\*", "install arbitrary packages"),
    (r"^uv pip install\*", "install arbitrary packages"),
    (r"^uv add\*", "install arbitrary packages"),
    (r"^cargo install\*", "install arbitrary packages"),
    (r"^gem install\*", "install arbitrary packages"),
]


def parse_agent_bash_rules(filepath: Path) -> dict[str, str]:
    content = filepath.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter = parts[1]
    lines = frontmatter.split("\n")
    rules: dict[str, str] = {}
    in_bash = False
    for line in lines:
        if line.strip() == "bash:":
            in_bash = True
            continue
        if in_bash:
            if line.startswith("    "):
                match = re.match(r'\s*"([^"]+)":\s*(\w+)', line)
                if match:
                    rules[match.group(1)] = match.group(2)
            elif line.strip() and not line.startswith("    "):
                break
    return rules


def parse_global_bash_rules(filepath: Path) -> dict[str, str]:
    with open(filepath) as f:
        config = json.load(f)
    return config.get("permission", {}).get("bash", {})


def check_rules(rules: dict[str, str], source: str) -> list[str]:
    is_global = source == "opencode.json"
    violations = []
    for pattern, action in rules.items():
        if action != "allow":
            continue
        for entry in DANGEROUS_PATTERNS:
            regex, reason = entry[0], entry[1]
            scope = entry[2] if len(entry) > 2 else "all"
            if scope == "agent" and is_global:
                continue
            if re.match(regex, pattern):
                violations.append(f'  [{source}] "{pattern}": {action}\n    -> {reason}')
                break
    return violations


def main() -> None:
    all_violations: list[str] = []

    if OPENCODE_JSON.exists():
        rules = parse_global_bash_rules(OPENCODE_JSON)
        all_violations.extend(check_rules(rules, "opencode.json"))

    if AGENTS_DIR.exists():
        for agent_file in sorted(AGENTS_DIR.glob("*.md")):
            rules = parse_agent_bash_rules(agent_file)
            all_violations.extend(check_rules(rules, f"agents/{agent_file.name}"))

    if not all_violations:
        print("OK: No dangerous permission rules found.")
        sys.exit(0)

    print("FAIL: Dangerous permission rules detected:\n")
    for v in all_violations:
        print(v)
    print(f"\nTotal: {len(all_violations)} violation(s)")
    sys.exit(1)


if __name__ == "__main__":
    main()
