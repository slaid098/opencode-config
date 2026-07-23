# ADR-010: merge_pr tool wrapper for orchestrator model

## Статус
Accepted

## Контекст
MERGE phase выполнялась main agent'ом через raw `gh pr merge` (см. `run-pipeline/SKILL.md` Rules + `pipeline-status.py` `NEXT_ACTIONS["MERGE"]`). Это конфликтует с pure-orchestrator моделью: main agent = plan/delegate/verify, НЕ исполняет mutations напрямую. Tool-led philosophy (обёртка side-effects в tools, imported из приватного репо как принцип без локального ADR) предписывает: (1) сохранить orchestrator-контракт, (2) дать uniform API surface, (3) централизовать guard logic.

Дополнительно: `config/` paths в `run-pipeline/SKILL.md` (`config/scripts/scaffold-handoff.sh`) stale после PR#23 (миграция config/ → .opencode/). Phase 0 "load issue skill" ambiguity — противоречит PR#28 issue-skill rewrite (full subagent delegation).

## Решение
- Created `merge_pr` TS tool (`.opencode/tools/merge-pr.ts`) — wrapper для `gh pr merge N --squash --delete-branch` через `spawnSync`. Built with `@opencode-ai/plugin` `tool({...})` pattern (matching `pipeline-status.ts`, `spec-status.ts`), auto-discovered из `.opencode/tools/` — без регистрации в `opencode.json`.
- `run-pipeline/SKILL.md`: replaced raw `gh pr merge` в Rules → `merge_pr({ pr_number: M })` tool call; added explicit `Template F (merge)` MERGE phase section (tool call, error handling, re-loop).
- `run-pipeline/SKILL.md` Phase 0: "load issue skill" → "dispatch subagent (general) with instruction to load `issue` skill" (pure orchestrator).
- `run-pipeline/SKILL.md` Template A: `config/scripts/scaffold-handoff.sh` → `.opencode/scripts/scaffold-handoff.sh`.
- `pipeline-status.py` `NEXT_ACTIONS["MERGE"]`: "смержить PR (gh pr merge N...)" → "вызвать merge_pr tool ({pr_number: N})...". Placeholder `N` для `get_next_action` replace.
- Тест `test_get_next_action` MERGE assertion обновлён.

## Альтернативы
- **Dedicated merger subagent** — отклонено. Subagent = task executor с own context, ослабляет security guard (merge by main agent, НЕ subagent — established guard). `merge_pr` tool вызывается main agent'ом напрямую — preserves guard + orchestrator-контракт.
- **Explicit exception в AGENTS.md** ("main agent may run gh pr merge") — отклонено. Violates pure-orchestrator model, создаёт precedent для других raw-bash exceptions.
- **Keep raw bash + документировать** — отклонено. Orchestrator conflict не resolved, tool-led philosophy не honoured.
- **`check-permissions.py` runtime merge guard в tool** — рассмотрено, отложено. `check-permissions.py` сейчас только linting (CI-time), не runtime guard. Реализация runtime guard — follow-up (potential ADR).

## Связанные
- Tool-led philosophy — referenced из приватного репо как принцип (без локального ADR-номера).
- PR#28 (issue-skill full subagent delegation) — Phase 0 ambiguity resolved в том же направлении.
- PR#29 (commands rename: `/pipeline-driver` → `/run-pipeline`) — tool names (`pipeline_status`, `merge_pr`) independent от command names.
- Issue #10 (AGENTS.md orchestrator rewrite) — pending, references `/run-pipeline`.