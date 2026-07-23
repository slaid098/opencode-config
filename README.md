# opencode-config

Docker-based AI coding assistant with persistent memory — opencode configuration.

## Quick start

### Docker

```bash
git clone https://github.com/slaid098/opencode-config.git
cd opencode-config
mkdir -p app_data/{workspaces,ssh}
cp .env.example .env  # fill in your keys
docker compose up -d
```

Access at http://localhost:4096.

### Bare (without Docker)

```bash
git clone https://github.com/slaid098/opencode-config.git
cd opencode-config
opencode  # .opencode/ auto-discovered
```

## Structure

- `AGENTS.md` — global orchestrator rules (main agent = plan only, all via subagents)
- `.opencode/` — project-local config (auto-discovered, zero env var)
  - `agents/` — subagent definitions (docs-reviewer, memory-syncer, reviewer)
  - `commands/` — slash commands (run-pipeline, spec, configure-opencode)
  - `skills/` — skill definitions (14 skills)
  - `tools/` — custom tools (pipeline-status, spec-status, merge-pr)
  - `scripts/` — Python scripts (pipeline-status, spec-status, check-adr-refs, etc.)
  - `opencode.json` — main config (providers, MCP servers, permissions)
- `app_data/workspaces/` — agent working directory
- `app_data/ssh/` — SSH keys (not in git)
- `app_data/opencode-memory/` — persistent memory (separate git repo)
- `src/` — Python RAG CLI (second-brain)
- `docs/` — handoffs, decisions (ADRs), project map
- `.github/workflows/` — CI workflows (ubuntu-latest)

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `AI_PROVIDER_BASE_URL` | AI provider API URL |
| `AI_PROVIDER_API_KEY` | AI provider API key |
| `OPENCODE_SERVER_PASSWORD` | opencode server password |
| `GITHUB_TOKEN` | GitHub personal access token |
| `CONTEXT7_API_KEY` | Context7 MCP API key |
| `ANTIDETECT_BROWSER_MCP_URL` | Antidetect browser MCP URL (optional) |

## Memory setup

Memory uses `@mathew-cf/opencode-memory` plugin (hybrid search: ripgrep + local RAG).

- `OPENCODE_MEMORY_DIR` env var points to memory directory (default: `app_data/opencode-memory/`)
- Run `.opencode/scripts/setup-memory.sh` to initialize memory repo

## License

MIT — see [LICENSE](LICENSE)