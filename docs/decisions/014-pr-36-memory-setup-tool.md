# ADR-014: Memory setup tool with deterministic init

## Статус
Accepted

## Контекст
После миграции memory в отдельный репо `slaid098/opencode-memory` (PR#17/24) память стала невидима для агента в Docker-окружении. `docker-compose.yml` указывал `OPENCODE_MEMORY_DIR=/root/workspace/app_data/opencode-memory`, но mount `./app_data/workspaces:/root/workspace` делал путь несуществующим — memory физически лежала вне доступного контейнеру пути. Ручная инициализация (clone, hook, rag index) не воспроизводилась детерминированно: агент не должен импровизировать bash-команды, а raw скрипт `setup-memory.sh` (PR#24) не был idempotent и не покрывал edge-cases (wrong remote, missing hook, offline pull).

Нужен tool, который агент вызывает из главного чата (pure-orchestrator model, ADR-010): tool делегирует в bash script, script детерминированно приводит memory в known-good state за 6 шагов.

## Решение
TS tool `memory-setup.ts` (thin wrapper, 0 args, паттерн `tunnel.ts`) + bash script `setup-memory.sh` (детерминированный flow, `set -euo pipefail`):

1. `mkdir -p MEMORY_DIR` — если директории нет
2. `git clone` (если нет `.git`) | `git pull --ff-only` (если есть)
3. `git remote set-url` — если origin ≠ REMOTE
4. post-commit hook install — если отсутствует или содержимое ≠ expected
5. `rag index` — если `.rag` нет (best-effort, rag CLI опционален)
6. `echo status`

Idempotent: 3x прогона = одинаковый state. `OPENCODE_MEMORY_REMOTE` обязательна (exit 1 если не set) — `.env.example` предоставляет значение; отсутствие = config error, не silent fallback. `OPENCODE_MEMORY_DIR` имеет default `/root/.local/share/opencode/opencode-memory` (через существующий `./app_data:/root/.local/share/opencode` mount).

post-commit hook: `#!/bin/bash\ngit push origin master 2>/dev/null || true` — auto-push после каждого `memory_save`, синхронизирует memory-репо с remote без ручного шага.

## Альтернативы
- Raw bash (агент вызывает `setup-memory.sh` напрямую через bash permission) — отклонено: нарушает pure-orchestrator model (ADR-010), агент не должен запускать arbitrary bash из главного чата
- MCP plugin init hook (auto-init при старте opencode) — отклонено: plugin init не ставит post-commit hook и не перестраивает RAG index; нет явного control когда init происходит
- Default value для `OPENCODE_MEMORY_REMOTE` (silent fallback на `https://github.com/slaid098/opencode-memory.git`) — отклонено: спека требует exit 1 при отсутствии env var; silent fallback маскирует config errors (пользователь может случайно клонировать чужой репо)