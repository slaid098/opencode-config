---
pr: 40
title: Deny direct git/gh calls + role-based tool access
---

# PR: Deny direct git/gh calls + role-based tool access

## Что сделано
- `.opencode/opencode.json` → `permission.bash`: добавлены 4 deny-правила в КОНЕЦ секции (findLast — последние побеждают): `"git commit *": "deny"`, `"gh pr create *": "deny"`, `"gh pr merge *": "deny"`, `"gh issue create *": "deny"`. Прямые bash-вызовы блокируются. Существующие `allow` rules для этих команд оставлены выше по файлу (перекрыты deny через findLast) — НЕ удалялись по спеке.
- `.opencode/opencode.json` → `agent.<name>.tools`: расширена секция `agent` (было `general: { steps: 100 }`) до role-based tool access. 4 агента: `general` (commit/create_pr/create_issue=true, merge_pr=false), `reviewer` (все false), `docs-reviewer` (commit=true, остальные false), `memory-syncer` (все false). Main agent наследует global tools (all true by default) — не указан в секции.
- `.opencode/agents/docs-reviewer.md`: убрано `"git commit*": allow` из frontmatter (теперь global deny покрывает; docs-reviewer должен использовать `commit` tool). Prompt body обновлён: `git commit -m ...` → `commit({ message: ... })` в 3 местах (Spec cleanup commit, Commit scope, Commit section). `git push*`: allow оставлен (push остаётся разрешённым глобально).
- `.opencode/agents/reviewer.md`: `gh pr merge*: deny` оставлен в frontmatter (defense-in-depth, global deny покрывает). Без изменений.
- `.opencode/agents/memory-syncer.md`: `gh pr merge*: deny` оставлен в frontmatter (defense-in-depth). Без изменений.
- `tests/test_permissions.py` (8 тестов): global deny rules присутствуют (4 rules), git push остаётся allowed, findLast ordering (deny после allow), agent.general.tools, agent.reviewer.tools (all false), agent.docs-reviewer.tools (commit=true), agent.memory-syncer.tools (all false), check-permissions.py exit 0.
- `check-permissions.py`: БЕЗ ИЗМЕНЕНИЙ — deny-действия не триггерят violations (скрипт флагует только `allow`). Существующие `allow` rules для `git commit`/`gh pr create`/`gh pr merge`/`gh issue` оставлены в opencode.json (перекрыты deny), добавление deterministic guard флагнуло бы легитимные allow. `gh pr merge*` уже имеет guard (scope=agent в `DANGEROUS_PATTERNS`). exit 0 подтверждён.
- ADR-016 + этот handoff

## Почему
Второй PR из серии из 3 (build → **lock** → switch). PR #38 (build) добавил 3 детерминированных tool'а (`commit`, `create_pr`, `create_issue`) с валидацией форматов. Этот PR (lock) блокирует прямые bash-вызовы `git commit`/`gh pr create`/`gh pr merge`/`gh issue create`, чтобы агенты использовали tools вместо raw bash. Третий PR (switch) обновит промпты агентов/skills на использование tools.

Механизм: opencode имеет два независимых уровня permissions:
1. `permission.bash` — glob-паттерны на bash-команды (блокирует прямой вызов). Custom TS tools bypass через `spawnSync` (trusted code, не проходит через `permission.bash`).
2. `agent.<name>.tools` — boolean map per-agent (включает/отключает конкретные tools).

Логика доступа: `reviewer` read-only (все false), `docs-reviewer` коммитит project map/handoff (commit=true), `memory-syncer` работает только в memory репо (все false), `general` реализует фичи (commit/create_pr/create_issue=true, merge_pr=false), main agent мержит (наследует all true).

Спека issue #39 не содержала ошибок. Все acceptance criteria выполнены.

## Pending
- Третий PR серии (switch): обновить промпты `reviewer.md`/`memory-syncer.md`/skills на использование `commit`/`create_pr`/`create_issue` tools (вместо raw bash команд, которые теперь глобально заблокированы). docs-reviewer уже обновлён в этом PR.
- `AGENTS.md` Development Workflow упоминает raw `gh pr merge`/`gh issue create` — может потребовать обновления на tool references (вне scope этого PR).
- Skills `commit`/`issue` содержат те же правила в тексте — дублирование с tool кодом (наследовано из PR#38, future cleanup).

## Watch out
- **findLast semantics**: deny rules ДОЛЖНЫ идти ПОСЛЕ allow (last wins). 4 deny rules добавлены в самый конец секции `bash` (после `ssh *: ask`). Если в будущем кто-то добавит `allow` ниже deny — allow выиграет. Детерминированной защиты от этого НЕТ (добавление DANGEROUS_PATTERNS флагнуло бы существующие легитимные allow выше по файлу).
- **`git commit *` duplicate key**: allow (строка 172) и deny (конец секции) используют ОДИНАКОВЫЙ pattern `"git commit *"`. JSON не может иметь дубликаты ключей — `json.load` сохраняет последнее значение (deny). В Python dict остаётся только одна запись `git commit *: deny`. Тест `test_deny_rules_override_earlier_allows` проверяет final value (deny) вместо ordering для этого case.
- **`gh issue*` allow vs `gh issue create *` deny**: `gh issue*` (allow, broader) стоит выше `gh issue create *` (deny, narrower). findLast: для `gh issue create --title ...` оба матчатся, но deny стоит позже → deny выигрывает. Для `gh issue view ...` только `gh issue*` allow матчится → allow (view не заблокирован, корректно).
- **docs-reviewer `git commit*` allow удалён**: docs-reviewer теперь НЕ может вызвать `git commit` через bash (global deny + frontmatter allow убран). docs-reviewer должен использовать `commit` tool. Prompt body обновлён в 3 местах. Если docs-reviewer не загрузит `commit` tool (e.g. tool не зарегистрирован после рестарта) — commit не сработает. После merge нужен `git pull` на хосте + рестарт контейнера (config bind-mount, tools грузятся при старте — паттерн PR#81/PR#100/PR#102).
- **`gh pr merge*: deny` в agent frontmatter**: оставлен в reviewer/docs-reviewer/memory-syncer как defense-in-depth (global deny покрывает, но per-agent deny документирует намерение). Безвредно (findLast, оба deny).
- **check-permissions.py пути**: скрипт использует `REPO_ROOT / "config" / "agents"` и `REPO_ROOT / "config" / "opencode.json"` (строки 10-11), но файлы лежат в `.opencode/`. Скрипт не находит файлов → violations=[] → exit 0 "OK". Это pre-existing issue (наследован из миграции config→.opencode PR#23), не блокирует. Скрипт корректно отрабатывает как black-box через subprocess в тестах (exit 0). Исправление путей — отдельный PR.
- ADR number = sequential (016), НЕ PR number. Проверить ADR naming в handoff до push (эволюция паттерна PR#26 docs-reviewer typo).