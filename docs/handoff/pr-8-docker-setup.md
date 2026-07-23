# PR: Docker setup

## Что сделано
- docker-compose.yml: 2 services (dind + opencode), 4 bind mounts, opencode_network
- Dockerfile: node:20-slim, uv, gh, chromium, docker.io, opencode-ai, repomix
- .env.example: cleaned of private IPs/domains/tunnel UUID, placeholder only
- Убрано: cloudflared (tunnel → отдельный репо), digital_factory_app_network (self-contained network)

## Почему
Docker-based AI coding assistant. Публичный релиз — очищено от приватной инфраструктуры.
Source: `/root/workspace/opencode/` (ветка fix/pipeline-status/review-next-by-verdict) — docker-compose.yml, Dockerfile, .env.example.

## Pending
- AGENTS.md bind-mount volume — добавляется в #10

## Watch out
- `.env` gitignored — пользователь создаёт из `.env.example` (`cp .env.example .env`). `docker compose config` без `.env` падает с `env file .env not found` — это expected, не баг.
- .env.example НЕ содержит реальных ключей — placeholder only.
- CLOUDFLARE_TUNNEL_TOKEN= (optional) — оставлен как placeholder, tunnel перенесён в отдельный репо.
- ANTIDETECT_BROWSER_MCP_URL=http://localhost:8765/mcp — дефолт local, для remote переопределить в `.env` на `http://<server-ip>:8765/mcp`.
- GIT_AUTHOR/COMMITTER_EMAIL изменён с `agent@slaid098.dev` на `agent@opencode.local` — публичный репо без приватного домена.
- OPENCODE_MEMORY_DIR=/root/workspace/app_data/opencode-memory — путь внутри контейнера; bind mount `./app_data/workspaces:/root/workspace` маппит host→container, так что memory лежит в `./app_data/workspaces/app_data/opencode-memory` на хосте. Возможен нюанс с layout — проверить в runtime.

## Файлы
- `docker-compose.yml` — 2 services (dind, opencode), network `opencode_network`, 4 bind mounts
- `Dockerfile` — node:20-slim + apt (ca-certs, curl, git, ssh, autossh, python3, make, g++, chromium, gnupg, docker.io, ffmpeg) + uv + gh + opencode-ai + repomix
- `.env.example` — AI provider, OpenCode server, GitHub, Context7, Telegram, Redis, Cloudflare (optional), Antidetect Browser MCP
- `docs/handoff/pr-8-docker-setup.md` — этот файл (PR number исправлен post-create)
- `docs/decisions/004-pr-8-docker-setup.md` — ADR-004