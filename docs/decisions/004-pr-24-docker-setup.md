# ADR-004: Docker setup (public, cleaned)

## Статус
Accepted

## Контекст
Docker-based AI coding assistant с persistent memory. Старый репо `/root/workspace/opencode/` содержал `cloudflared` (Cloudflare Tunnel client), external network `digital_factory_app_network` (shared с monorepo digital_factory), приватные IPs (`80.85.139.21`), приватный домен `ai.slaid098.dev` в `AI_PROVIDER_BASE_URL`, tunnel UUID `f97e66a5-...` в комментариях `.env.example`. Публичный релиз `slaid098/opencode-config` требует очистки от приватной инфраструктуры.

Архитектура нового репо: 4 bind mount'а (`.opencode`/`app_data`/`app_data/workspaces`/`app_data/ssh:ro`) вместо старого `config/`+`sandbox_workspace`.

## Решение
- 2 services в `docker-compose.yml`: `dind` (docker:dind, privileged, 2 CPU / 4G) + `opencode` (build from Dockerfile, 3 CPU / 6G)
- Network `opencode_network` (self-contained, НЕ external)
- 4 bind mounts: `./.opencode`→`/root/.config/opencode`, `./app_data`→`/root/.local/share/opencode`, `./app_data/workspaces`→`/root/workspace`, `./app_data/ssh`→`/root/.ssh:ro`
- `docker-compose.yml`: `env_file: .env` (gitignored, user copies from `.env.example`)
- `Dockerfile`: node:20-slim + apt (ca-certificates, curl, git, openssh-client, autossh, python3, make, g++, chromium, gnupg, docker.io, ffmpeg) + uv + gh (via apt keyring) + `npm install -g opencode-ai repomix --unsafe-perm` + Puppeteer ENV (system chromium)
- `.env.example`: placeholder only (`your-api-key-here`, `https://your-ai-provider.example.com/v1/`)
- Убрано: `cloudflared` install (Dockerfile строки 33-34 оригинала), `digital_factory_app_network` external network, IP `80.85.139.21`, домен `ai.slaid098.dev`, tunnel UUID `f97e66a5-...`
- `GIT_AUTHOR/COMMITTER_EMAIL` изменён с `agent@slaid098.dev` на `agent@opencode.local`

## Альтернативы
- **Сохранить cloudflared** — отклонено. Публичный репо, tunnel = приватная инфраструктура (named tunnel `slaid098-dev` привязан к конкретному Cloudflare account). Tunnel вынесен в отдельный приватный репо.
- **Docker compose без dind** — отклонено. opencode-ai использует Docker для sandboxed execution (субагенты запускают `docker run`), без dind теряется ключевая возможность.
- **Сохранить external network `digital_factory_app_network`** — отклонено. External network shared с monorepo `digital_factory` на конкретной машине, не self-contained. Заменён на локальную `opencode_network`.
- **Hardcode приватных IPs/domains в `.env.example`** — отклонено. Публичный репо, секреты в `.env` (gitignored), `.env.example` — документация с placeholder'ами.

## Последствия
- `docker compose config` без `.env` падает с `env file .env not found` — expected, пользователь обязан `cp .env.example .env` перед `docker compose up`.
- `OPENCODE_MEMORY_DIR=/root/workspace/app_data/opencode-memory` — путь внутри контейнера маппится через bind mount в `./app_data/workspaces/app_data/opencode-memory` на хосте. Layout может потребовать корректировки после runtime-тестирования.
- AGENTS.md bind-mount volume не включён в этот PR — добавляется в #10.