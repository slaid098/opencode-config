# ADR-006: Skills cleanup batch

## Статус
Accepted

## Контекст
После миграции skills из config/ → .opencode/ (#7), 7 skills содержали устаревшие пути, противоречия с AGENTS.md, stale templates.

## Решение
Atomic batch: 7 skills в одном PR. Minor fixes only (no rewrites). Rewrites вынесены в #12, #13.

## Альтернативы
- Отдельный PR на каждый skill — отклонено (7 PR для minor fixes = overhead)
- Полный rewrite всех skills — отклонено (scope creep, rewrites в #12/#13)