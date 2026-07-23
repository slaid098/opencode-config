# Project Map

opencode-config — Docker-based AI coding assistant with persistent memory (opencode configuration).

## Structure

```
opencode-config/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # Lint, test, typecheck, complexity (bootstrap + output-based skip)
│   │   ├── permissions-check.yml  # .opencode/scripts/check-permissions.py validator (step-level skip)
│   │   └── adr-check.yml           # ADR cross-reference validator (.opencode/scripts/check-adr-refs.py)
│   └── dependabot.yml              # pip + github-actions ecosystem updates
├── .opencode/                      # Project-local opencode config (auto-discovery, zero env var) — PR#23
│   ├── agents/
│   │   ├── docs-reviewer.md        # Docs validation subagent (project map + handoff + ADR)
│   │   ├── memory-syncer.md        # Distills gotchas from handoffs into opencode-memory
│   │   └── reviewer.md             # Code review subagent (verdict APPROVE|REQUEST_CHANGES)
│   ├── commands/
│   │   ├── opencode-config.md      # /opencode-config — edit opencode.json
│   │   ├── pipeline-driver.md      # /pipeline-driver — 7-phase PR pipeline
│   │   └── spec-driver.md          # /spec-driver — 9-phase spec generation
│   ├── skills/
│   │   ├── add-skill/SKILL.md      # Create new opencode skill
│   │   ├── branch/SKILL.md         # Branch naming conventions
│   │   ├── code-standards/SKILL.md # Universal code style rules
│   │   ├── commit/SKILL.md         # Commit message conventions
│   │   ├── get-project-map/SKILL.md # Maintain docs/project-map/
│   │   ├── issue/SKILL.md          # GitHub issue creation
│   │   ├── memory/SKILL.md         # opencode-memory usage guide
│   │   ├── opencode-config/SKILL.md # Canonical rule: write to .opencode/
│   │   ├── pipeline-driver/SKILL.md # 7-phase pipeline orchestration
│   │   ├── python-development/SKILL.md # Python dev patterns
│   │   ├── release/SKILL.md        # Tag + GitHub Release
│   │   ├── repo-init/SKILL.md      # New repository bootstrap
│   │   ├── run-tests/SKILL.md      # Test runner guide
│   │   └── spec-driver/SKILL.md    # 9-phase spec generation
│   ├── tools/
│   │   ├── pipeline-status.ts      # pipeline_status tool wrapper
│   │   └── spec-status.ts          # spec_status tool wrapper
│   ├── scripts/
│   │   ├── check-adr-refs.py       # ADR cross-reference validator (adr-check.yml)
│   │   ├── check-permissions.py    # Permissions validator (permissions-check.yml)
│   │   ├── observability.py        # OTel spans for tools
│   │   ├── pipeline-status.py      # 7-phase oracle (gh PR + CI polling)
│   │   ├── scaffold-handoff.sh     # Scaffold handoff + ADR stubs
│   │   ├── setup-memory.sh         # opencode-memory bootstrap
│   │   └── spec-status.py          # 9-phase spec oracle
│   ├── opencode.json               # MCP servers, providers, permissions, agents, plugins
│   ├── package.json                # npm deps for tools/*.ts
│   └── .gitignore                  # Ignores node_modules, etc.
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

- `src/` — Python RAG CLI (second-brain) — after #5 (PR#17)
- `tests/` — pytest test suite — after #5

## Update Protocol

Updated by docs-reviewer subagent on each PR. Reflects tracked files only (`git ls-files`).
