# ADR-005: Remove echo allow from reviewer agent

## Статус
Accepted

## Контекст
reviewer.md имеет edit: deny (read-only контракт). Но "echo *": allow позволял echo "x" > file.txt — bypass write restriction.

## Решение
Удалить "echo *": allow из bash allow-list. Debug вывод через pwd/ls/cat (уже разрешены).

## Альтернативы
- Обновить Rule 10 вместо удаления — отклонено (soft guard в prompt менее надёжен чем deterministic permission guard)
- Оставить echo но запретить > — отклонено (bash permission matching не поддерживает гранулярные операторы)