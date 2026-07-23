# ADR-001: CI bootstrap job + output-based skip conditions

## Статус

Accepted

## Контекст

Chicken-and-egg: pipeline-driver требует CI ✅ для merge, но CI не может работать без #7 (scripts) и #5 (src/tests). Нужен способ иметь CI runs на каждом PR даже когда src/ и scripts/ ещё не мигрированы.

## Решение

1. ci.yml: bootstrap job (checkout + file check + always passes) — гарантирует CI run → pipeline_status CI phase = DONE
2. lint/test/typecheck/complexity jobs: `if: needs.bootstrap.outputs.has_src == 'true'` — skip без src/*.py
3. permissions-check/adr-check: step-level file checks (checkout → check script exists → conditional run)

## Альтернативы

- `hashFiles()` в job-level `if` — отклонено: GitHub Actions не распознаёт `hashFiles` как функцию в job-level `if` (ошибка "Unrecognized function: 'hashFiles'"). Заменено на output-based conditions.
- Объединить #5+#6+#7 в один PR — отклонено (пользователь хочет атомарные PR)
- Merge без pipeline-driver (admin override) — отклонено (нарушает pipeline протокол)
- ci.yml без modifications (перенести как есть) — отклонено (CI падает без src/tests, нет runs → AMBIGUOUS → pipeline STOP)
