# ADR-012: docs skeleton + public README

## Статус
Accepted

## Контекст
New public repo needs docs/ skeleton for handoffs/ADRs + complete README for users.

## Решение
- docs/ .gitkeep files (skeleton)
- README.md: Quick start (Docker + Bare), Structure, Configuration, Memory, License
- docs/project-map/ already created in PR #18

## Альтернативы
- Keep minimal README — отклонено (public repo needs full docs)
- Skip docs/ skeleton — отклонено (pipeline-driver requires docs/handoff/ + docs/decisions/)