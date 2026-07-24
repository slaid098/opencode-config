# ADR-015: Validation tools (commit, create-pr, create-issue)

## Статус
Accepted (2026-07-24)

## Контекст
AGENTS.md содержал детерминированные правила форматов для commits, PRs, issues в текстовом виде (skills `commit`/`issue`). Агент читал правила и выполнял `git commit`/`gh pr create`/`gh issue create` через raw bash. Это нарушало pure-orchestrator model (ADR-010/PR#30): main agent = plan/delegate/verify, НЕ исполняет mutations напрямую. Правила в тексте не валидировались автоматически — агент мог допустить ошибку формата, и CI/review ловил её поздно.

Нужны tools, которые агент вызывает из главного чата: tool валидирует формат (regex, language, headings, length), и только при success исполняет side-effect (git commit, gh pr create, gh issue create). На error — возвращает правила + examples (recent commits), агент корректирует и повторяет.

## Решение
3 TS tool'а, паттерн `merge-pr.ts` (thin wrapper → spawnSync → `cwd: context.worktree`):

1. **commit.ts** — 1 arg `message`. Валидация: single-line, regex `^(feat|fix|chore|docs|refactor|test|style|perf)\([^)]+\): .{1,72}$`, English only (`/[\u0400-\u04FF]/`), staged files exist (`git diff --cached --name-only`). На error — правила + 5 recent commits. На success — `git commit -m <msg>`, возвращает `Committed: <msg>`

2. **create-pr.ts** — 3 args (`title`, `body`, `issue_number?`). Валидация: title regex (≤72), English title, body headings (`## Что сделано`, `## Почему`), body Russian (Cyrillic), `issue_number` → append `\n\nCloses #N`. На success — `gh pr create`, возвращает `PR created: <url>`

3. **create-issue.ts** — 3 args (`title`, `body`, `labels?`). Валидация: title regex (≤80 для issue), English title, body headings (`## Контекст`, `## Задача`, `## Критерии приемки`), body Russian. Labels → `--label <comma-joined>`. На success — `gh issue create`, возвращает `Issue created: <url>`

Tools auto-discovered через `@opencode-ai/plugin` — НЕ регистрируются в opencode.json (подтверждение паттерна PR#30/#36).

`tests/_ts_loader.mjs` расширен: новый `exec_stub_json` mode для multi-arg tools (JSON args + sequential stub responses). Существующие modes не изменены — обратная совместимость сохранена.

## Альтернативы
- Validation в skills (текстовые правила, агент читает и следует) — отклонено: не enforced автоматически, агент может ошибиться, ошибки ловятся поздно (CI/review). Tools валидируют в коде — deterministic, testable
- Single generic "git-helper" tool с mode arg — отклонено: нарушает single-responsibility, усложняет validation logic (каждый mode имеет разные rules). 3 отдельных tool'а чище
- Validation в opencode.json permission rules — отклонено: permission rules — security guards (allow/deny bash commands), не format validators. Format validation — domain logic, принадлежит tool коду
- Python tools вместо TS — отклонено: существующий паттерн репо — TS tools (`merge-pr.ts`, `pipeline-status.ts`, `memory-setup.ts`). Consistency важнее personal preference