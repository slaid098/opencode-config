# Project Map

opencode-config — Docker-based AI coding assistant with persistent memory (opencode configuration).

## Structure

```
opencode-config/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # Lint, test, typecheck, complexity (bootstrap + output-based skip)
│   │   ├── permissions-check.yml  # .opencode/scripts/permissions.py validator (step-level skip)
│   │   └── adr-check.yml           # ADR cross-reference validator (step-level skip)
│   └── dependabot.yml              # pip + github-actions ecosystem updates
├── docs/
│   ├── handoff/                   # PR handoffs (pr-<N>-<slug>.md)
│   ├── decisions/                 # ADRs (NNN-pr-<N>-<slug>.md)
│   └── project-map/               # This file — structure snapshot
├── app_data/
│   ├── workspaces/                # Agent working directory (.gitkeep)
│   └── ssh/                       # SSH keys, not in git (.gitkeep)
├── .editorconfig
├── .gitignore
├── .python-version
├── LICENSE
└── README.md
```

## Pending (future PRs)

- `.opencode/` — global opencode config (agents, skills, tools, scripts) — after #7
- `src/` — Python RAG CLI (second-brain) — after #5 (PR#17)
- `tests/` — pytest test suite — after #5

## Update Protocol

Updated by docs-reviewer subagent on each PR. Reflects tracked files only (`git ls-files`).
