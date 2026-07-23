---
name: commit
description: Analyse git history of any project and suggest commit messages that match existing conventions.
---

## Процесс

1. Запустить `git log --oneline -30`
2. Если коммиты есть:
   - Извлечь все уникальные `type(scope):` паттерны
   - Составить список реальных scopes проекта
   - Следовать найденному стилю
3. Если коммитов нет (новый проект):
   - Базовый формат: `type(scope): description`
   - Типы: `feat | fix | chore | docs | refactor | test | style | perf`
   - Scope по умолчанию: спросить пользователя
   - Description отвечает на **why** (не what)
   - Без точки в конце
   - Max ~72 символа

## Type

| Type | When |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `chore` | Maintenance, cleanup, dependencies, config |
| `refactor` | Code restructuring, no behavior change |
| `docs` | AGENTS.md, SKILL.md, README only |
| `test` | Adding or fixing tests |
| `style` | Formatting, linting, whitespace only |
| `perf` | Performance improvements |

## Branch naming

`type/scope/description` — kebab-case, из тех же scopes.

## Пример вывода для агента

Если `git log` показывает:
```
chore(config): add docker proxy
fix(docker): resolve no-sandbox
feat(agents.md): add guidelines
```

То scopes: `config`, `docker`, `agents.md`. Новый коммит пишется в том же стиле.
