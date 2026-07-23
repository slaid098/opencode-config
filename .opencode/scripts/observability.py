#!/usr/bin/env python3
"""Parse opencode log for permission denials and tool errors."""

import re
import sys
from collections import defaultdict
from pathlib import Path

LOG_PATH = Path.home() / ".local" / "share" / "opencode" / "log" / "opencode.log"


def parse_line(line):
    """Extract fields from a log line."""
    ts_match = re.search(r"timestamp=(\S+)", line)
    run_match = re.search(r"run=(\S+)", line)
    ts = ts_match.group(1) if ts_match else "?"
    run = run_match.group(1) if run_match else "?"
    return ts, run


def _process_line(line, sessions, denials, errors):
    """Classify a single log line into sessions/denials/errors."""
    if "message=created" in line and "agent=" in line:
        ts, run = parse_line(line)
        agent_match = re.search(r"agent=(\S+)", line)
        session_match = re.search(r"id=(\S+)", line)
        title_match = re.search(r'title="([^"]*)"', line)
        agent = agent_match.group(1) if agent_match else "unknown"
        session = session_match.group(1) if session_match else "?"
        title = title_match.group(1) if title_match else ""
        sessions[run] = {"agent": agent, "session": session, "title": title}

    elif "action.action=deny" in line:
        ts, run = parse_line(line)
        pattern_match = re.search(r'pattern="([^"]*)"', line)
        perm_match = re.search(r"permission=(\S+)", line)
        pattern = pattern_match.group(1) if pattern_match else "?"
        perm = perm_match.group(1) if perm_match else "?"
        denials.append({"ts": ts, "run": run, "pattern": pattern, "perm": perm})

    elif "message=process" in line and "level=ERROR" in line:
        ts, run = parse_line(line)
        error_match = re.search(r"error=(\S+)", line)
        session_match = re.search(r"session\.id=(\S+)", line)
        error = error_match.group(1) if error_match else "unknown"
        session = session_match.group(1) if session_match else "?"
        errors.append({"ts": ts, "run": run, "error": error, "session": session})


def main():
    if not LOG_PATH.exists():
        print("Log file not found: {LOG_PATH}")
        sys.exit(1)

    sessions = {}
    denials = []
    errors = []

    with open(LOG_PATH) as f:
        for line in f:
            _process_line(line, sessions, denials, errors)

    if not denials and not errors:
        print("No denials or errors found in log.")
        return

    print("# Observability Report")
    print(f"# Log: {LOG_PATH}")
    print(f"# Denials: {len(denials)} | Errors: {len(errors)}")
    print()

    if denials:
        print("## Permission Denials\n")
        by_agent = defaultdict(list)
        for d in denials:
            info = sessions.get(d["run"], {"agent": "unknown", "session": "?", "title": ""})
            by_agent[info["agent"]].append(d)

        for agent, items in sorted(by_agent.items()):
            print(f"### {agent} ({len(items)} denials)\n")
            for d in items:
                info = sessions.get(d["run"], {"session": "?"})
                print(f"- {d['ts']} | `{d['pattern']}` | {d['perm']} | {info['session']}")
            print()

    if errors:
        print("## Process Errors\n")
        for e in errors[-20:]:
            info = sessions.get(e["run"], {"agent": "unknown"})
            print(f"- {e['ts']} | {info['agent']} | {e['error']} | {e['session']}")


if __name__ == "__main__":
    main()
