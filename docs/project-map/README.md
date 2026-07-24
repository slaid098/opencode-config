# Project Map

opencode-config — Docker-based AI coding assistant with persistent memory (opencode configuration). Runs in Docker via `docker-compose.yml` (dind + opencode services).

Root `AGENTS.md` — orchestrator directive (chat = plan only, all via subagents) + global rules (commits, PRs, code style, language RU). Auto-loaded for project + bind-mounted globally in container — PR#31.

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
│   │   ├── configure-opencode.md   # /configure-opencode — edit opencode.json
│   │   ├── run-pipeline.md          # /run-pipeline — 7-phase PR pipeline
│   │   └── spec.md                  # /spec — 9-phase spec generation
│   ├── skills/
│   │   ├── add-skill/SKILL.md      # Create new opencode skill
│   │   ├── branch/SKILL.md         # Branch naming conventions
│   │   ├── code-standards/SKILL.md # Universal code style rules
│   │   ├── commit/SKILL.md         # Commit message conventions
│   │   ├── get-project-map/SKILL.md # Maintain docs/project-map/
│   │   ├── issue/SKILL.md          # GitHub issue creation
│   │   ├── memory/SKILL.md         # opencode-memory usage guide
│   │   ├── configure-opencode/SKILL.md # Canonical rule: write to .opencode/
│   │   ├── run-pipeline/SKILL.md # 7-phase pipeline orchestration
│   │   ├── python-development/SKILL.md # Python dev patterns
│   │   ├── release/SKILL.md        # Tag + GitHub Release
│   │   ├── repo-init/SKILL.md      # New repository bootstrap
│   │   ├── run-tests/SKILL.md      # Test runner guide
│   │   └── spec/SKILL.md           # 9-phase spec generation
│   ├── tools/
│   │   ├── merge-pr.ts            # merge_pr tool wrapper (orchestrator-safe gh pr merge) — PR#30
│   │   ├── memory-setup.ts         # memory_setup tool wrapper (0 args, calls setup-memory.sh) — PR#36
│   │   ├── pipeline-status.ts      # pipeline_status tool wrapper
│   │   ├── spec-status.ts          # spec_status tool wrapper
│   │   └── tunnel.ts               # Cloudflare tunnel toggle tool (start/stop без args) — PR#34
│   ├── scripts/
│   │   ├── check-adr-refs.py       # ADR cross-reference validator (adr-check.yml)
│   │   ├── check-permissions.py    # Permissions validator (permissions-check.yml)
│   │   ├── observability.py        # OTel spans for tools
│   │   ├── pipeline-status.py      # 7-phase oracle (gh PR + CI polling)
│   │   ├── scaffold-handoff.sh     # Scaffold handoff + ADR stubs
│   │   ├── setup-memory.sh         # opencode-memory bootstrap (deterministic 6-step flow, idempotent) — PR#36
│   │   ├── spec-status.py          # 9-phase spec oracle
│   │   └── tunnel.sh               # Cloudflare tunnel toggle bash (named mode via CLOUDFLARE_TUNNEL_TOKEN) — PR#34
│   ├── opencode.json               # MCP servers, providers, permissions, agents, plugins
│   ├── package.json                # npm deps for tools/*.ts
│   └── .gitignore                  # Ignores node_modules, etc.
├── docs/
│   ├── handoff/                   # PR handoffs (pr-<N>-<slug>.md)
│   ├── decisions/                 # ADRs (NNN-pr-<N>-<slug>.md)
│   └── project-map/               # This file — structure snapshot
├── src/                           # Python RAG CLI (second-brain) — PR#17
│   └── memory/
│       ├── __init__.py
│       ├── __main__.py            # Entry point for `python -m memory`
│       ├── cli.py                 # CLI commands
│       ├── embedder.py            # Embedding via AI_PROVIDER_API_URL (env-only)
│       ├── index.py               # Indexing
│       └── search.py              # Search
├── tests/                         # pytest + TS/MJS test suite — PR#17
│   ├── _ts_loader.mjs             # TS test loader (imports pipeline-status.ts / spec-status.ts)
│   ├── test_check_adr_refs.py     # adr-check.yml validator
│   ├── test_check_permissions.py  # permissions-check.yml validator
│   ├── test_cli.py                # src/memory/cli.py
│   ├── test_embedder.py           # src/memory/embedder.py (mocks AI_PROVIDER_API_URL)
│   ├── test_index.py              # src/memory/index.py
│   ├── test_memory_setup_tool.py  # .opencode/tools/memory-setup.ts (via _ts_loader.mjs) — PR#36
│   ├── test_memory_setup_tool.ts  # TS wrapper test (mjs loader) — PR#36
│   ├── test_observability.py      # .opencode/scripts/observability.py
│   ├── test_pipeline_status.py    # .opencode/scripts/pipeline-status.py (REVIEW verdict branching)
│   ├── test_pipeline_status_adr.py
│   ├── test_pipeline_status_ci.py
│   ├── test_pipeline_status_tool.py
│   ├── test_pipeline_status_tool.ts  # TS wrapper test (mjs loader)
│   ├── test_search.py             # src/memory/search.py
│   ├── test_setup_memory.py       # .opencode/scripts/setup-memory.sh (mock remote, idempotency) — PR#36
│   ├── test_spec_status.py        # .opencode/scripts/spec-status.py
│   └── test_spec_status_tool.py
├── pyproject.toml                 # Python project (uv, ruff, pytest config)
├── uv.lock                        # Locked deps for Python project
├── .pre-commit-config.yaml        # ruff + UV hooks
├── docker-compose.yml             # 2 services (dind + opencode), opencode_network, 4 bind mounts — PR#24
├── Dockerfile                     # node:20-slim + uv + gh + chromium + docker.io + opencode-ai + repomix + cloudflared — PR#24, PR#34
├── .env.example                   # Placeholder-only env template (user copies to .env) — PR#24, PR#34 (TUNNEL_DOMAIN), PR#36 (OPENCODE_MEMORY_REMOTE/DIR)
├── app_data/
│   ├── workspaces/                # Agent working directory (.gitkeep)
│   └── ssh/                       # SSH keys, not in git (.gitkeep)
├── .editorconfig
├── .gitignore
├── .python-version
├── AGENTS.md                       # Orchestrator directive + global rules (bind-mounted globally) — PR#31
├── LICENSE
└── README.md
```

## Pending (future PRs)

- `.opencode/scripts/pipeline-status.py` fix `610452f` — PR#7 (config/scripts/ migration)
- `.opencode/tools/` TS wrappers — PR#7 (config/tools/ migration)

## Update Protocol

Updated by docs-reviewer subagent on each PR. Reflects tracked files only (`git ls-files`).
