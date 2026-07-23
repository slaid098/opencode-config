# PR: docs skeleton + README rewrite

## Что сделано
- docs/ skeleton: .gitkeep files for docs/, decisions/, handoff/ (if missing)
- README.md: full public README (Quick start Docker + Bare, Structure, Configuration, Memory setup, License)
- docs/project-map/README.md: already exists (from PR #18), updated if needed

## Почему
Public repo needs complete README for users. docs/ skeleton for future PR handoffs/ADRs.

## Pending
- Нет (финальный PR миграции)

## Watch out
- README references AGENTS.md (#10), /run-pipeline (#14), merge_pr (#16) — all merged
- .env.example from #8, docker-compose from #8
- Memory plugin @mathew-cf/opencode-memory