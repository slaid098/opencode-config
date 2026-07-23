# opencode-config

Docker-based AI coding assistant with persistent memory — opencode configuration.

## Quick start

```bash
git clone https://github.com/slaid098/opencode-config.git
cd opencode-config
mkdir -p app_data/{workspaces,ssh}
cp .env.example .env  # fill in your keys
docker compose up -d
```

Access at http://localhost:4096.

## Structure

- `.opencode/` — global opencode config (agents, skills, tools, scripts)
- `app_data/workspaces/` — agent working directory
- `app_data/ssh/` — SSH keys (not in git)
- `app_data/opencode-memory/` — persistent memory (separate git repo)
- `src/` — Python RAG CLI (second-brain)
