# ADR-016: Deny direct git/gh bash calls + role-based tool access

## Статус
Accepted (2026-07-24)

## Контекст
PR #38 добавил 3 детерминированных TS tool'а (`commit`, `create_pr`, `create_issue`) с встроенной валидацией форматов. Но агенты могли всё ещё вызывать `git commit`/`gh pr create`/`gh pr merge`/`gh issue create` через raw bash (разрешено в `permission.bash`), обходя валидацию tools. Это нарушало pure-orchestrator model (ADR-010/PR#30) и контракты форматов (AGENTS.md rules не enforced).

opencode имеет два независимых уровня permissions:
1. `permission.bash` — glob-паттерны на bash-команды (findLast — последние побеждают). Custom TS tools bypass через `spawnSync` (trusted code, не проходит через `permission.bash`).
2. `agent.<name>.tools` — boolean map per-agent (включает/отключает конкретные tools для конкретного агента).

Нужно: (1) заблокировать прямые bash-вызовы мутаций, не блокируя tools, (2) настроить role-based access — кто из subagent'ов какие tools может вызывать.

## Решение

### 1. Global deny rules в `permission.bash` (`.opencode/opencode.json`)
4 deny-правила в КОНЕЦ секции `bash` (findLast — last wins, перекрывают более ранние allow):
- `"git commit *": "deny"` — блокирует прямой `git commit`, `commit` tool bypass'ит
- `"gh pr create *": "deny"` — блокирует прямой `gh pr create`, `create_pr` tool bypass'ит
- `"gh pr merge *": "deny"` — блокирует прямой `gh pr merge`, `merge_pr` tool bypass'ит
- `"gh issue create *": "deny"` — блокирует прямой `gh issue create`, `create_issue` tool bypass'ит

`git push *` остаётся `allow` (НЕ добавлен deny — push нужен для пуша веток).

### 2. Role-based tool access в `agent.<name>.tools`
| Agent | commit | create_pr | create_issue | merge_pr |
|---|---|---|---|---|
| general | ✅ | ✅ | ✅ | ❌ |
| reviewer | ❌ | ❌ | ❌ | ❌ |
| docs-reviewer | ✅ | ❌ | ❌ | ❌ |
| memory-syncer | ❌ | ❌ | ❌ | ❌ |
| main (orchestrator) | ✅ | ✅ | ✅ | ✅ (наследует global all-true) |

Main agent НЕ указан в `agent` секции → наследует global tools (all true by default). Явные restrictions только для subagents.

### 3. docs-reviewer frontmatter + prompt
`"git commit*": allow` убран из frontmatter (global deny покрывает). Prompt body: `git commit -m ...` → `commit({ message: ... })` в 3 местах. docs-reviewer теперь использует `commit` tool для коммита project map/handoff.

### 4. `DANGEROUS_PATTERNS` — БЕЗ ИЗМЕНЕНИЙ
Новые deny rules не требуют deterministic guards: (1) deny-действия не триггерят violations (скрипт флагует только `allow`), (2) существующие `allow` rules оставлены в opencode.json (перекрыты deny через findLast), добавление guard флагнуло бы легитимные allow. `gh pr merge*` уже имеет guard (scope=agent).

## Альтернативы
- **Удалить существующие allow rules вместо добавления deny** — отклонено: спека issue #39 явно говорит "добавить deny rules в конец" (findLast), не "удалить allow". Удаление allow нарушило бы другие use cases (e.g. `gh issue*` allow покрывает `gh issue view`, `gh issue list`). Deny в конце точечно перекрывает только create-команды.
- **Добавить DANGEROUS_PATTERNS для `git commit *: allow`/`gh pr create *: allow`/`gh issue create *: allow`** — отклонено: флагнуло бы существующие легитимные allow rules выше по файлу (которые перекрыты deny через findLast, но всё ещё присутствуют в JSON). CI упал бы на валидных конфигах. Глобальный `gh pr merge*: allow` намеренно оставлен для main agent (guard scope=agent пропускает global).
- **Per-agent `git commit*: deny` в frontmatter вместо global** — отклонено: global deny покрывает всех агентов одной строкой. Per-agent deny в 4 frontmatter файлах = дублирование. Global + defense-in-depth per-agent (только для `gh pr merge*`, уже есть) — достаточно.
- **Запретить `git push *` тоже** — отклонено: push нужен для пуша feature-веток в remote (PR workflow). Push НЕ мутация в том же смысле, что commit/create/merge — push синхронизирует локальные коммиты с remote. Issue явно запрещает deny на `git push *`.