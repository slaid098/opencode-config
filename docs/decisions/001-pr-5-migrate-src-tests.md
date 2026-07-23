# ADR-001: Migrate src/ second-brain + tests from fix-branch

## Статус

Accepted

## Контекст

Миграция Python RAG CLI (`second-brain`) из приватного репо в публичный. Source: ветка `fix/pipeline-status/review-next-by-verdict` (содержит фикс pipeline-status REVIEW verdict branching). Hardcoded приватный API endpoint `ai.slaid098.dev` в embedder.py.

## Решение

- Копировать файлы из fix-ветки (не master) — фикс включён автоматически
- Strip `ai.slaid098.dev` → env-only `AI_PROVIDER_API_URL`
- Rename `slaid098/opencode` → `slaid098/opencode-config` в URLs и тестах

## Альтернативы

- Дропнуть `src/memory/` полностью (memory plugin `@mathew-cf/opencode-memory` покрывает RAG) — отклонено, second-brain используется как standalone CLI
- Копировать из master + отдельный PR для фикса — отклонено, fix-ветка fast-forward, проще взять целиком
