---
pr_number: <PR-NUMBER>
title: Memory setup tool with deterministic init
---

# PR: Memory setup tool with deterministic init

## Что сделано
- `.opencode/tools/memory-setup.ts` — TS tool wrapper (0 args, вызывает `bash .opencode/scripts/setup-memory.sh`, паттерн `tunnel.ts`)
- `.opencode/scripts/setup-memory.sh` — переписан: детерминированный flow (6 шагов: mkdir, clone/pull, remote check, hook, rag index, status), `set -euo pipefail`, idempotent
- `docker-compose.yml` — `OPENCODE_MEMORY_DIR` исправлен: `/root/workspace/app_data/opencode-memory` → `/root/.local/share/opencode/opencode-memory` (через существующий `./app_data:/root/.local/share/opencode` mount)
- `.env.example` — добавлены `OPENCODE_MEMORY_REMOTE` (обязательный) + `OPENCODE_MEMORY_DIR` (опциональный, default в script)
- `.gitignore` — добавлен `app_data/opencode-memory/` (memory — отдельный репо, clone target, не в config)
- `tests/test_setup_memory.py` — 6 pytest тестов с mock remote (`git init --bare`): fresh init, existing repo, wrong remote, missing hook, idempotent (3x), no remote env
- `tests/test_memory_setup_tool.ts` — 2 TS теста (документационные, по паттерну `test_pipeline_status_tool.ts`): success, failure
- `tests/test_memory_setup_tool.py` — 4 Python теста через `_ts_loader.mjs`: load, success, failure, cwd propagation
- ADR-014 + этот handoff

## Почему
После миграции memory в отдельный репо (`slaid098/opencode-memory`) память стала невидима в Docker: `docker-compose.yml` указывал путь через mount `./app_data/workspaces:/root/workspace`, но memory лежала вне этого mount. Ручная инициализация не воспроизводилась детерминированно. Нужен tool для pure-orchestrator model (ADR-010): агент вызывает tool из главного чата, tool делегирует в script, script клонирует remote, ставит post-commit hook для auto-push, перестраивает RAG index. Idempotent — каждый запуск = одинаковый result, безопасно вызывать многократно.

Спека issue содержала противоречие: одновременно указан default для `OPENCODE_MEMORY_REMOTE` (`https://github.com/slaid098/opencode-memory.git`) и требование "exit 1 если не set". Решено в пользу acceptance criteria + test spec: env var обязательна, default убран, `.env.example` предоставляет значение. Зафиксировано в ADR-014 (Альтернативы).

## Pending
- `rag` CLI нет на CI runner — шаг 5 скрипта best-effort (warn + continue, не exit 1). Когда rag будет установлен в Dockerfile, index будет перестраиваться автоматически. Вне scope этого PR.
- `master` branch hardcoded в скрипте и hook. Memory remote использует `master` (не `main`). Если remote переедет на `main` — потребуется обновление `BRANCH` переменной.

## Watch out
- `OPENCODE_MEMORY_REMOTE` обязателен — без него скрипт exit 1. Не добавляйте default обратно: silent fallback маскирует config errors (можно клонировать чужой репо).
- `OPENCODE_MEMORY_DIR` default = `/root/.local/share/opencode/opencode-memory` — соответствует mount `./app_data:/root/.local/share/opencode` в docker-compose.yml. Memory физически лежит в `opencode-config/app_data/opencode-memory/` на хосте (отдельный git репо, gitignored).
- post-commit hook выполняет `git push origin master 2>/dev/null || true` — silent failure при offline. Memory commits сохраняются локально, push произойдёт при следующем online-коммите.
- `git pull --ff-only` — если локальная история разошлась с remote (force-push или rebase), pull упадёт. Скрипт ловит это (`|| echo skipped`) и продолжает, но memory останется неактуальной. Ручное разрешение требуется.
- `rag index` шаг best-effort: если `rag` CLI не установлен, скрипт пропускает шаг (warn, не error). RAG index перестроится когда rag станет доступен.
- Tools auto-discovered через @opencode-ai/plugin — НЕ нужно регистрировать в opencode.json.
- TS-тест (`test_memory_setup_tool.ts`) документационный — CI гоняет Python-версию (`test_memory_setup_tool.py`) через `_ts_loader.mjs` (bun нет на runner).