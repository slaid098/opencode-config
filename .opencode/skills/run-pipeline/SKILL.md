---
name: run-pipeline
description: Автономный исполнитель PR-пайплайна. Делегирует 7 фаз subagent'ам, не импровизирует порядок, не мержит при красном CI.
---

# Run Pipeline

Автономная процедура-loop для проведения PR через 7 фаз. Source of truth для
порядка и действий — `pipeline_status` tool.

## ПРОТОКОЛ (ЖЁСТКО)

Каждая итерация (БЕЗ ИСКЛЮЧЕНИЙ):

1. Вызови tool `pipeline_status({pr_number: M})` — вернёт статус всех фаз + строку `NEXT: <action>`.
2. Если вывод содержит `Status: COMPLETE` → финальный репорт пользователю, exit.
3. Если вывод содержит `AMBIGUOUS` → репорт пользователю с причиной, STOP.
4. Иначе — исполни action из строки `NEXT:` (используй prompt templates A-E ниже).
5. 1 строка прогресса пользователю (формат: `✅ <phase> — <action executed>`).
6. Re-loop (шаг 1).

### ЗАПРЕЩЕНО

- ЛЮБОЙ action БЕЗ предшествующего вызова `pipeline_status` = protocol violation.
- Импровизировать порядок. Решать сам какой subagent запускать — читай `NEXT:`.
- Пропускать вызов `pipeline_status`, даже если «кажется, что фаза уже ✅» — скрипт решает.
- Делать bash `sleep` для ожидания CI — `pipeline_status` сам блокирует до 5 мин (polling Actions API внутри `check_ci`). Один вызов → финальный статус.
- Merge при CI ❌ (transitive guard в скрипте).
- Использовать `--admin` flag для `gh pr merge`.
- Параллелить subagents (последовательно: action → `pipeline_status` → next action).

### Остановы

- Subagent error → 1 retry, потом STOP + report пользователю.
- `AMBIGUOUS` в выводе `pipeline_status` → STOP + report.
- 5 итераций подряд без прогресса (та же фаза ❌) → STOP + report.

## Phase 0: Bootstrap

1. Если задача описана в чате, а не issue → load `issue` skill, создай GitHub
   issue N (через subagent с `issue` skill, чтобы не засорять контекст).
2. Запусти subagent (general type) с prompt template A → PR M с `Closes #N` в
   body. Subagent вернёт PR номер M.
3. Войди в loop ПРОТОКОЛ выше.

## Prompt templates

### Template A (implement_issue)

```
Реализуй issue #N в текущем репо (working directory = корень репо).
1. Checkout new branch `type/scope/kebab-description` от master.
2. Реализуй по спеке issue (точно, без отклонений). Если спека содержит ошибки,
   зафикь и продолжай — не додумывай.
3. Создай handoff + ADR: `bash config/scripts/scaffold-handoff.sh M <slug>`
   (M — будет PR номер, используй placeholder `<PR-NUMBER>` в handoff
   frontmatter, потом исправишь после `gh pr create`).
4. Коммиты в формате `type(scope): description` (≤72 chars, English, no
   period, no body unless necessary). Минимум 3-4 логических коммита.
5. Push и создай PR:
   `gh pr create --title "type(scope): description" --body "## Что сделано\n...\n\n## Почему\n...\n\nCloses #N"`
6. После получения PR номера — исправь placeholder `<PR-NUMBER>` в handoff
   frontmatter, отдельный коммит `docs(handoff): set PR number`, push.
7. Верни PR номер M.
```

### Template B (docs-review)

```
Review PR#M в текущем репо (pre-merge, режим docs).
1. `gh pr checkout M`.
2. Анализируй структурные изменения: `git diff origin/master...HEAD --stat`.
3. Сравни с `docs/project-map/` — обнови если structural changes.
4. Валидируй handoff `docs/handoff/pr-M-*.md`: 4 секции (Что сделано, Почему,
   Pending, Watch out) заполнены осмысленно (не пустые плейсхолдеры).
5. Валидируй ADR `docs/decisions/*-pr-M-*.md`: 4 секции (Статус, Контекст,
   Решение, Альтернативы).
6. Если криво — почини (edit: allow).
7. `git add docs/project-map/ docs/handoff/ docs/decisions/ && git commit -m
   "docs: update project map + handoff + ADR" && git push`.
8. **ВСЕГДА** оставь PR comment (даже если structural changes нет) — это
   детерминированный marker для `check_docs` в pipeline-status.py. Без comment
   pipeline блокируется на DOCS phase.
   `gh pr comment M --body "## Docs Review Summary\n- Project map: ...\n- Handoff: ...\n- ADR: ...\n\n### Verdict: APPROVE|FIXED|NO_CHANGES"`.
   Heading `## Docs Review Summary` — обязательно (regex `Docs Review`).
```

### Template C (code_review)

```
Review PR#M в текущем репо.
1. `gh pr view M --json headRefName,body,title`.
2. `git diff origin/master...HEAD`.
3. Load project skills: `find .opencode/skills/ -name "SKILL.md"`, грузи каждый
   через `skill("<name>")`.
4. Проверь: code quality, architecture, error handling, security, testing,
   duplication, project-specific rules, PR hygiene, handoff/ADR (quick check).
5. Оставь review как PR comment (НЕ `gh pr review --approve` — GitHub блокирует
   self-approve):
   `gh pr comment M --body "## Code Review Summary\n...\n### Verdict: APPROVE|REQUEST_CHANGES"`.
   6. НЕ МЕРДЖИТЬ — merge делает основной агент через run-pipeline.
```

### Template D (fix_ci)

```
CI упал на PR#M. Чтобы получить <run-id>: `gh run list --branch <headRefName> --limit 1 --json databaseId,conclusion`.
Log: `gh run view <run-id> --log-failed` output:
<log>
1. `gh pr checkout M`.
2. Проанализируй log, найди причину.
3. Исправь (минимальные изменения, whitespace/formatting/logic fix).
4. Коммит `fix(ci): <description>`, push.
5. Не трогай логику unrelated файлов.
```

### Template E (memory_sync)

```
Дистиллируй PR#M в memory file
`app_data/opencode-memory/repos/{host}/{org}/{repo}.md`
(путь относительно корня репо; `{host}/{org}/{repo}` вычисли через
`git remote get-url origin` — см. `memory-syncer.md:38`).
1. Прочитай `docs/handoff/pr-M-*.md` и `docs/decisions/*-pr-M-*.md` с master
   (`git checkout master && git pull`).
2. Найди durable gotchas (не статусы, не "сейчас делаем"). Паттерны, указатели,
   non-obvious API quirks.
3. Добавь записи формата `- [YYYY-MM-DD, PR#M] <summary>` в конец файла
   (секция "Handoff digest").
4. Квитанция ВСЕГДА (даже если durable нет): `- [date, PR#M] — (нет durable-записей)`.
5. `memory_save` для commit + reindex + push.
6. Проверь `git status` основного репо — если staged что-то в `app_data/`,
   репорт пользователю (guard от случайного коммита в master).
```

## API Restrictions

Использовать только Actions API (`pipeline_status`, `gh run list`, `gh run view`, `gh api repos/.../actions/runs`). **Запрещено** `gh pr checks` и `gh pr view --json statusCheckRollup` — 403 на fine-grained PAT (scope `Checks: read` не существует).

## Rules

- `pipeline_status` — единственный source of truth для порядка шагов и действий.
- Скрипт read-only (только `gh api`/`gh pr view`, без мутаций).
- После каждой фазы → 1 строка прогресса юзеру.
- Если subagent error → 1 retry, потом STOP + report пользователю.
- `gh pr merge M --squash --delete-branch` (без `--admin`).
- Если reviewer вердикт `REQUEST_CHANGES` → запусти subagent (general) с prompt "fix reviewer comments: <list>", commit, push → re-loop (`pipeline_status` проверит CI автоматически).