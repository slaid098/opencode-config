# ADR-002: CI bootstrap job + hashFiles conditions

## Статус

Accepted

## Контекст

Chicken-and-egg: pipeline-driver требует CI ✅ для merge, но CI не может работать без #7 (scripts) и #5 (src/tests). Нужен способ иметь CI runs на каждом PR даже когда src/ и scripts/ ещё не мигрированы.

## Решение

1. ci.yml: bootstrap job (always passes) — гарантирует CI run → pipeline_status CI phase = DONE
2. lint/test/typecheck/complexity jobs: `if: hashFiles('src/**/*.py')` — skip без src/
3. permissions-check/adr-check: `if: hashFiles('.opencode/scripts/...')` — skip без scripts/

## Альтернативы

- Объединить #5+#6+#7 в один PR — отклонено (пользователь хочет атомарные PR)
- Merge без pipeline-driver (admin override) — отклонено (нарушает pipeline протокол)
- ci.yml без modifications (перенести как есть) — отклонено (CI падает без src/tests, нет runs → AMBIGUOUS → pipeline STOP)
