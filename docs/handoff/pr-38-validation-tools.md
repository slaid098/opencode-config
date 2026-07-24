---
pr_number: 38
title: Validation tools (commit, create-pr, create-issue)
---

# PR: Validation tools (commit, create-pr, create-issue)

## Что сделано
- `.opencode/tools/commit.ts` — TS tool wrapper (1 arg `message`), валидация: single-line, regex `type(scope): description` (≤72), English only (no Cyrillic), staged files exist. На error — правила + 5 recent commits. Паттерн `merge-pr.ts` (spawnSync, `cwd: context.worktree`)
- `.opencode/tools/create-pr.ts` — TS tool wrapper (3 args: `title`, `body`, `issue_number?`), валидация: title regex (≤72), English title, body headings (`## Что сделано`, `## Почему`), body Russian (Cyrillic), `issue_number` → append `Closes #N`. Возвращает `PR created: <url>`
- `.opencode/tools/create-issue.ts` — TS tool wrapper (3 args: `title`, `body`, `labels?`), валидация: title regex (≤80 для issue), English title, body headings (`## Контекст`, `## Задача`, `## Критерии приемки`), body Russian. Labels → `--label <comma-joined>`. Возвращает `Issue created: <url>`
- `tests/_ts_loader.mjs` — расширен: новый mode `exec_stub_json` для multi-arg tools (JSON args + sequential stub responses). `buildExecArgsFromJson` + `buildStubSequencer` helper functions. Существующие `load`/`exec_stub`/`exec_real` modes не изменены
- `tests/test_commit_tool.ts` — 7 TS тестов (документационные, паттерн `test_pipeline_status_tool.ts`): valid, no scope, Cyrillic, multiline, >72, no staged, wrong type
- `tests/test_create_pr_tool.ts` — 6 TS тестов: valid, missing scope, missing headings, Latin-only, issue linkage
- `tests/test_create_issue_tool.ts` — 7 TS тестов: valid, >80, missing sections, Latin-only, labels
- `tests/test_commit_tool.py` — 9 Python тестов через `_ts_loader.mjs` (exec_stub_json): load, valid, no scope, Cyrillic, multiline, >72, no staged, wrong type, cwd propagation
- `tests/test_create_pr_tool.py` — 8 Python тестов: load, valid, missing scope, missing headings, Latin-only, issue linkage, cwd propagation
- `tests/test_create_issue_tool.py` — 10 Python тестов: load, valid, >80, 80 boundary, missing sections, Latin-only, labels, cwd propagation
- ADR-015 + этот handoff

## Почему
Оптимизация AGENTS.md: вынос детерминированной логики (commits, PRs, issues) в tools с встроенной валидацией. Все правила форматов переносятся из skills в код tools — агент вызывает tool, tool валидирует и исполняет. Это первый PR из серии из 3 (build → lock → switch). Паттерн `merge-pr.ts` (PR#30, ADR-010): thin TS wrapper → spawnSync → `context.worktree` как cwd. Tools auto-discovered через `@opencode-ai/plugin` — НЕ зарегистрированы в opencode.json (подтверждение паттерна PR#30/#36).

Спека issue содержала 2 противоречия, зафиксированы (не додумывал, продолжал по спеке):
1. **create-issue.ts labels spread bug**: `["--label", ...labels]` создаёт `["--label", "bug", "enhancement"]`, но `gh` принимает `--label` с одним значением. Исправлено на `["--label", labels.join(",")]` → `--label bug,enhancement` (gh comma-синтаксис)
2. **Cyrillic check unreachable**: спека требует validation order: headings (Cyrillic) → Cyrillic check. Поскольку headings сами содержат Cyrillic (`## Что сделано`, `## Контекст`), body прошедший heading check всегда проходит Cyrillic check. Latin-only body падает на heading check, не на Cyrillic. Тесты adjusted: `test_latin_only_body` проверяет reachable behavior (heading error), не unreachable Cyrillic error. Cyrillic check оставлен как defense-in-depth (если headings изменятся на English в будущем)

## Pending
- AGENTS.md не обновлялся — вне scope этого PR. Правила форматов теперь дублируются (AGENTS.md текст + tools код). Future PR может заменить AGENTS.md rules на "use commit/create-pr/create-issue tools" references
- Skills `commit`/`issue` содержат те же правила в тексте — дублирование с tool кодом. Future cleanup может сократить skills до "load tool" pointers
- `test_latin_only_body` test name сохранён для совместимости со спекой, но проверяет heading error (не Cyrillic). Если validation order изменится (Cyrillic перед headings) — test нужно будет обновить

## Watch out
- `_ts_loader.mjs` расширен новыми функциями (`buildExecArgsFromJson`, `buildStubSequencer`, `exec_stub_json` mode). Существующие `exec_stub`/`exec_real`/`load` modes не изменены — обратная совместимость сохранена. Новые multi-arg tools (commit, create-pr, create-issue) используют `exec_stub_json`; существующие single-arg tools (pipeline-status, spec-status, memory-setup) продолжают использовать `exec_stub`
- `commit.ts` делает 2 spawnSync вызова на success path (git diff --cached, git commit) и до 2 на error path (git diff, git log). Тесты должны предоставлять последовательные stub responses
- create-issue.ts `labels` join: `["bug", "enhancement"]` → `"bug,enhancement"` (comma-joined, НЕ separate `--label` flags). gh CLI принимает comma-синтаксис
- Cyrillic check в create-pr/create-issue — defense-in-depth, фактически unreachable из-за heading checks (headings содержат Cyrillic). Не удалять — защита от будущих изменений headings на English
- Tools auto-discovered через `@opencode-ai/plugin` — НЕ нужно регистрировать в opencode.json (подтверждение паттерна PR#30/#36)
- TS-тесты (`test_*.ts`) — документационные, CI гоняет Python-версии через `_ts_loader.mjs` (bun нет на runner)
- ADR number = sequential (015), НЕ PR number. Эволюция известного паттерна (PR#26 docs-reviewer typo — записал PR number как ADR number)