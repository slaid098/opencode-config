# PR: run-pipeline rewrite + merge_pr tool

## Что сделано
- Created merge_pr TS tool (`.opencode/tools/merge-pr.ts`) — orchestrator-safe wrapper for `gh pr merge N --squash --delete-branch`. Built with `@opencode-ai/plugin` `tool({...})` pattern (matching `pipeline-status.ts` / `spec-status.ts`), auto-discovered from `.opencode/tools/` — no `opencode.json` registration needed.
- run-pipeline skill: replaced raw `gh pr merge` with `merge_pr({ pr_number: M })` tool call in Rules + added explicit `Template F (merge)` MERGE phase section.
- Fixed `config/scripts/scaffold-handoff.sh` → `.opencode/scripts/scaffold-handoff.sh` (Template A, step 3).
- Fixed Phase 0 ambiguity: "load issue skill" → "dispatch subagent (general) with instruction to load `issue` skill and create issue N" (main agent = pure orchestrator, не пишет issue body).
- Updated `pipeline-status.py` `NEXT_ACTIONS["MERGE"]`: "смержить PR (gh pr merge N...)" → "вызвать merge_pr tool ({pr_number: N})" (краткая форма — verbose вариант `— orchestrator-safe wrapper ...` превышал ruff E501 100 chars в тесте `test_get_next_action`; суть в tool call, детали в ADR-010).
- Updated test `test_pipeline_status.py::test_get_next_action` MERGE assertion to new string.
- Reformulated restriction line 29 to keep `--admin` ban but remove actionable raw-bash phrasing.

## Почему
MERGE by main agent via raw bash = orchestrator conflict (main agent = plan only, не исполняет mutations). `merge_pr` tool wrapper aligns with tool-led philosophy (обёртка side-effects в tools для orchestrator-контракта + uniform API + centralized guards). `config/` paths stale after PR#23 migration (config/ → .opencode/). Phase 0 ambiguity resolved in direction of PR#28 issue-skill rewrite (full subagent delegation). Stale "load pipeline-driver before PR" reference — не найдена в файле (переименование в #14 уже очистило); AGENTS.md ещё не существует (#10 не смержен), правки по AGENTS.md пропущены.

## Pending
- AGENTS.md orchestrator rewrite (#10) — references `/run-pipeline` + `/spec` (после rename в #29), collapse Dev Workflow + Pipeline section в pointer.
- `pipeline_status` oracle AMBIGUOUS bug — root cause не изолирован (PR#25-#29 pattern: oracle branch-matching стабильно не детектит runs от `always-ci.yml`). Надёжная альтернатива: `gh pr view N --json statusCheckRollup`.
- `opencode.json` tools section НЕ добавлен — tools auto-discovered из `.opencode/tools/*.ts` через `@opencode-ai/plugin` (проверено по существующим `pipeline-status.ts`, `spec-status.ts`). Issue спека предполагала регистрацию, но это не соответствует фактической конвенции репо.
- `check-permissions.py` merge guard НЕ реализован — `merge_pr` tool не имеет pre-flight security guard. Guard потенциально полезен (subagent deny merge), но `check-permissions.py` сейчас только linting permission rules, не runtime guard. Follow-up.

## Watch out
- `merge_pr` tool = TS wrapper, вызывает `gh pr merge --squash --delete-branch` через `spawnSync`. `cwd = context.worktree` (как в `pipeline-status.ts`).
- `pipeline_status` tool name unchanged (independent от command rename в #29). `merge_pr` — новый tool, экспонирует programmatic API.
- `get_next_action` в `pipeline-status.py` делает `action.replace("N", str(pr_number))` — placeholder в NEXT_ACTIONS должен быть `N` (НЕ `M`), иначе replace не сработает. MERGE action использует `{pr_number: N}`.
- run-pipeline skill renamed from pipeline-driver in #14/#29 (command `/run-pipeline`, skill dir `run-pipeline/`).
- `@opencode-ai/plugin` `tool({...})` pattern — НЕ plain `export default async function` (как в issue спеке). Issue спека показывала старый/упрощённый signature; фактическая конвенция репо — `tool({...})` с `args` schema.
- ADR numbering в этом репо sequential (001..009 на момент PR). ADRs из приватного `slaid098/opencode` (tool-led philosophy, subagent deny merge) НЕ мигрировали — references убраны, оставлен смысл (см. ADR-010 Контекст/Альтернативы).