# PR: CI workflows (ubuntu-latest) + dependabot

## Что сделано

- Перенесены .github/workflows/ (ci.yml, permissions-check.yml, adr-check.yml) + dependabot.yml
- runs-on: [self-hosted, linux] → ubuntu-latest (security risk для public repo)
- config/scripts/ → .opencode/scripts/ (пути в run steps + trigger paths)
- ci.yml: branches [master] → [main] (новый репо использует main)
- ci.yml: matrix 3.14 добавлен (ubuntu-latest поддерживает, self-hosted комментарий убран)
- ci.yml: добавлен bootstrap job (checkout + file check + always passes) + output-based skip conditions на lint/test/typecheck/complexity (skip без src/*.py)
- permissions-check.yml, adr-check.yml: step-level file checks (skip script execution без .opencode/scripts/)

## Почему

Bootstrapping: CI нужен до #7 (.opencode/ scripts) и #5 (src/tests). bootstrap job гарантирует CI run на каждом PR. Output-based conditions skip jobs которые не могут работать без src/ или scripts/.

## Отклонение от spec

- hashFiles() не распознан GitHub Actions в job-level `if` — заменён на output-based conditions (bootstrap job checks files, sets `has_src` output, jobs use `if: needs.bootstrap.outputs.has_src == 'true'`)
- permissions-check/adr-check: job-level `if` заменён на step-level file checks (checkout → check → conditional run)
- Дополнительно: branches [master] → [main], trigger paths config/ → .opencode/ (spec не упоминал)

## Pending

- После #7: permissions-check/adr-check jobs активируются (scripts доступны)
- После #5 (merge PR#17): lint/test/typecheck/complexity jobs активируются (src/ доступен)
- Matrix 3.14 — проверить совместимость с ubuntu-latest

## Watch out

- ci.yml НЕ перенесён "как есть" — добавлен bootstrap job + output-based conditions (адаптация для bootstrapping)
- hashFiles() не работает в GitHub Actions job-level `if` — это известное ограничение, см. ADR-002
- branches: [master] → [main] — старый репо использовал master, новый main
- trigger paths в permissions-check.yml/adr-check.yml: config/ → .opencode/ (config/ не существует в новом репо)
- permissions-check.yml, adr-check.yml — skip до #7 (нет .opencode/scripts/)
- dependabot.yml — без изменений (directory: "/config" для npm безвреден — директория не существует, dependabot просто пропустит)
