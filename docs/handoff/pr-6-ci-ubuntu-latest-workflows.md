# PR: CI workflows (ubuntu-latest) + dependabot

## Что сделано

- Перенесены .github/workflows/ (ci.yml, permissions-check.yml, adr-check.yml) + dependabot.yml
- runs-on: [self-hosted, linux] → ubuntu-latest (security risk для public repo)
- config/scripts/ → .opencode/scripts/ (пути в run steps + trigger paths)
- ci.yml: branches [master] → [main] (новый репо использует main)
- ci.yml: matrix 3.14 добавлен (ubuntu-latest поддерживает, self-hosted комментарий убран)
- ci.yml: добавлен bootstrap job (always passes) + hashFiles conditions на lint/test/typecheck/complexity (skip без src/)
- permissions-check.yml, adr-check.yml: hashFiles conditions (skip без .opencode/scripts/)

## Почему

Bootstrapping: CI нужен до #7 (.opencode/ scripts) и #5 (src/tests). bootstrap job гарантирует CI run на каждом PR. hashFiles conditions skip jobs которые не могут работать без src/ или scripts/.

## Pending

- После #7: permissions-check/adr-check jobs активируются (scripts доступны)
- После #5: lint/test/typecheck/complexity jobs активируются (src/ доступен)
- Matrix 3.14 — проверить совместимость с ubuntu-latest

## Watch out

- ci.yml НЕ перенесён "как есть" — добавлен bootstrap job + hashFiles (адаптация для bootstrapping)
- branches: [master] → [main] — старый репо использовал master, новый main
- trigger paths в permissions-check.yml/adr-check.yml: config/ → .opencode/ (config/ не существует в новом репо)
- permissions-check.yml, adr-check.yml — skip до #7 (нет .opencode/scripts/)
- dependabot.yml — без изменений (directory: "/config" для npm безвреден — директория не существует, dependabot просто пропустит)
