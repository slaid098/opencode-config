# ADR-011: Orchestrator AGENTS.md (root, bind-mount global)

## Статус
Accepted

## Контекст
Main agent должен быть pure orchestrator (chat = plan only, all via subagents). AGENTS.md должен быть global (all projects in container) + committed (source of truth).

## Решение
- AGENTS.md in root repo (committed, auto-loaded for project)
- Docker bind-mount ./AGENTS.md:/root/.config/opencode/AGENTS.md:ro (global for container)
- Orchestrator directive: all research/implementation via subagents, chat = plan only
- References /run-pipeline (#14) and merge_pr tool (#16)

## Альтернативы
- .opencode/AGENTS.md (project-local only) — отклонено (not global)
- config/AGENTS.md + bind-mount (old pattern) — отклонено (config/ → .opencode/ migration, ADR-002)