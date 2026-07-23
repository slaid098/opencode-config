---
name: spec-driver
description: Автономный исполнитель spec-генерации для нового проекта. Детерминированно ведёт агента по 9 фазам через spec_status tool. Главный агент — оркестратор, делегирует ВСЮ работу subagent'ам. Also when user says "создай спеку", "новый проект", "спецификация проекта", "spec", "project spec".
---

# Spec Driver

Автономная процедура-loop для генерации спецификации нового проекта. Source of
truth для порядка и действий — `spec_status` tool. На выходе — `docs/spec/`
(директория с файлами по фазам) + N GitHub issues, готовых для `/pipeline-driver`.

## ПРОТОКОЛ (ЖЁСТКО)

Каждая итерация (БЕЗ ИСКЛЮЧЕНИЙ):

1. Вызови tool `spec_status({})` — вернёт текущую фазу + строку `NEXT: <action>`.
2. Если вывод содержит `Status: COMPLETE` → финальный репорт пользователю, exit.
3. Если вывод содержит `AMBIGUOUS` → репорт пользователю с причиной, STOP.
4. Иначе — выполни action из строки `NEXT:` (используй prompt templates A-I ниже).
5. 1 строка прогресса пользователю (формат: `✅ <phase> — <action executed>`).
6. Re-loop (шаг 1).

### ЗАПРЕЩЕНО

- ЛЮБОЙ action БЕЗ предшествующего вызова `spec_status` = protocol violation.
- Импровизировать порядок. Решать сам какую фазу выполнять — читай `NEXT:`.
- Пропускать вызов `spec_status`, даже если «кажется, что фаза уже ✅» — скрипт решает.
- bash-запуск `python3 config/scripts/spec-status.py` — детерминированный deny-rule (см. ADR-NNN, аналог ADR-019). Только нативный tool `spec_status`.
- Главному агенту: edit/write/read файлов (всё через subagent), memory_search (через subagent), gh issue create (через subagent).
- Формулировать вопросы не из question templates ниже.
- Предлагать стек вне hardcoded default stack по типу проекта.
- Запускать /pipeline-driver (стоп на issues — дальше юзер сам).

### Остановы

- Subagent error → 1 retry, потом STOP + report пользователю.
- `AMBIGUOUS` в выводе `spec_status` → STOP + report.
- 3 итераций подряд без прогресса (та же фаза ❌) → STOP + report.

## Default stack по типам проекта (хардкод)

Общий для всех типов: Python 3.12+, uv, hatchling, ruff, mypy strict, pytest 90% cov, xenon, pre-commit, .editorconfig, .gitignore, LICENSE MIT, dependabot, CI.

- **backend**: FastAPI + uvicorn, Tortoise ORM + Aerich, pydantic-settings, Loguru
- **fullstack**: backend + frontend/ (React 19 + Vite + Biome + TS strict + Vitest + Knip + happy-dom)
- **mcp-server**: FastAPI + MCP SDK, Patchright/Playwright over CDP, X-API-Key
- **cli**: Typer (default) / click / argparse, hatchling build
- **bot**: aiogram 3.x, FastAPI webhook/polling, Tortoise (опц.), Pydantic AI (опц.)
- **worker**: Prefect flows + tasks, prefect.yaml, docker-compose worker profile

## 9 фаз

### Phase 0: DETECT (subagent, без вопроса юзеру)

Prompt template A (см. ниже).

### Phase 1: PROJECT_TYPE (вопрос юзеру + subagent)

Вопрос юзеру (один вопрос, multiple choice):

```
Выбери тип проекта:
[1] backend       — FastAPI + Tortoise, REST API, без frontend
[2] fullstack     — backend + React 19/Vite dashboard (monorepo)
[3] mcp-server    — MCP + REST сервер (Patchright/Playwright over CDP)
[4] cli           — Python CLI tool (Typer)
[5] bot           — Telegram bot (aiogram 3)
[6] worker        — Prefect flows / background jobs

Имя проекта (kebab-case): ___
Описание (1 строка): ___
GitHub owner [slaid098]: ___
```

Prompt template B (см. ниже).

### Phase 2: STACK (вопрос юзеру + subagent)

Вопрос юзеру — ТОЛЬКО развилки для выбранного типа:

```
backend:
- DB: [1] Postgres prod / [2] SQLite dev / [3] both / [4] no DB
- Auth: [1] none v1 / [2] JWT / [3] X-API-Key

fullstack:
- frontend: [1] React 19 (default) / [2] SvelteKit / [3] add later
- DB: (same as backend)
- Auth: (same as backend)

mcp-server:
- target: [1] BitBrowser / [2] custom / [3] generic
- auth: [1] X-API-Key / [2] none

cli:
- interface: [1] Typer (default) / [2] click / [3] argparse
- output: [1] rich / [2] plain / [3] loguru

bot:
- framework: [1] aiogram 3 (default) / [2] other
- mode: [1] polling / [2] FastAPI webhook
- Pydantic AI: [1] yes / [2] no
- DB: [1] Tortoise + SQLite / [2] Tortoise + Postgres / [3] no DB

worker:
- scheduler: [1] Prefect (default) / [2] APScheduler
- work_pool_name: ___ (default: <project>_pool)
- DB: [1] Tortoise + SQLite / [2] Tortoise + Postgres / [3] no DB
```

Prompt template C (см. ниже).

### Phase 3: MODULES (вопрос юзеру + subagent с добором)

Вопрос юзеру (free-form):

```
Какие модули/домены нужны? Например: "YouTube uploader, Telegram notifier, channel management".
Опиши модули (1 строка на модуль):
```

Prompt template D (см. ниже, с memory_search).

### Phase 4: DB_SCHEMA (вопрос юзеру + subagent)

Если в Phase 2 выбрано "no DB" → пропустить вопрос, subagent ставит `no_db: true` в `docs/spec/meta.md` (db-schema.md НЕ создаётся).

Иначе вопрос:

```
Опиши ключевые сущности и поля. Например:
"Channel: id UUID, platform enum, name str, is_active bool, metadata json
 Upload: id UUID, channel_id FK, video_url str, status enum, ..."
Стандартные поля (вшито, не спрашивай): id UUIDField pk, created_at, updated_at, status CharEnumField(StrEnum).
Опиши сущности:
```

Prompt template E (см. ниже).

### Phase 5: INFRA (вопрос юзеру + subagent)

Вопрос:

```
- Docker compose: [1] yes / [2] no
- Prefect: [1] yes / [2] no (если worker или backend с background jobs)
- MCP external: [1] yes (URL) / [2] no
- Tunnel (demo): [1] yes / [2] no
```

Prompt template F (см. ниже).

### Phase 6: ROADMAP (вопрос юзеру + subagent)

Вопрос (с default proposal):

```
Дефолтный roadmap (можешь править):
1. scaffolding — repo structure, CI, .gitignore, LICENSE (через repo-init skill)
2. core: <module 1> — ...
3. core: <module 2> — ...
4. auth (если выбран auth в Phase 2)
5. db migrations (если есть DB)
6. docker compose (если выбран в Phase 5)
7. frontend scaffolding (если fullstack)
Подтверди или отредактируй:
```

Prompt template G (см. ниже).

### Phase 7: CONFIRM (subagent читает, вопрос юзеру)

Prompt template H (см. ниже).

Вопрос юзеру:

```
Подтверди spec? [1] confirm / [2] edit Phase N (укажи номер)
```

Если edit → вернуться на указанную фазу (3, 4, 5 или 6), повторить, снова Confirm.

### Phase 8: EXECUTE (subagent, без вопроса юзеру)

Prompt template I (см. ниже, create issues).

Финальный репорт юзеру (после Phase 8):

```
Spec complete. Issues: #N1, #N2, ...
Запусти /pipeline-driver для issue #<первый> чтобы начать реализацию.
```

## Prompt templates

### Template A (detect / Phase 0)

```
Контекст: запуск spec-driver в репо <cwd>.
1. `git rev-parse --show-toplevel` → repo root.
2. Если docs/spec/meta.md существует → прочитай frontmatter, верни phase/status.
3. Если нет → создай docs/spec/meta.md с frontmatter:
   ---
   project: ''
   type: ''
   created: <today YYYY-MM-DD>
   phase: 0
   status: in_progress
   ---
   (создай директорию docs/spec/ через `mkdir -p docs/spec` если не существует)
4. `memory_search("reference repo")` → верни список релевантных memory paths.
5. Верни: {spec_exists: bool, current_phase: int, references: [...]}.
```

### Template B (project_type / Phase 1)

```
Обнови docs/spec/meta.md frontmatter для Phase 1 (PROJECT_TYPE).
Ответы юзера: type=<type>, project=<name>, description=<desc>, owner=<owner>.
1. Прочитай docs/spec/meta.md.
2. edit frontmatter: type=<type>, project=<name>, created=<today>, phase=1.
3. Создай файл docs/spec/context.md с описанием проекта из ответа юзера.
4. Верни: "done: type=<type>, project=<name>".
```

### Template C (stack / Phase 2)

```
Создай файл docs/spec/stack.md для Phase 2 (STACK).
Ответы юзера: <answers>.
Тип проекта: <type> (из frontmatter meta.md).
Default stack для типа (хардкод, добавить всегда):
- Общий: Python 3.12+, uv, hatchling, ruff, mypy strict, pytest 90% cov, xenon, pre-commit, .editorconfig, .gitignore, LICENSE MIT, dependabot, CI
- backend: FastAPI + uvicorn, Tortoise ORM + Aerich, pydantic-settings, Loguru
- fullstack: + frontend/ (React 19 + Vite + Biome + TS strict + Vitest + Knip + happy-dom)
- mcp-server: FastAPI + MCP SDK, Patchright/Playwright over CDP, X-API-Key
- cli: Typer (default) / click / argparse, hatchling build
- bot: aiogram 3.x, FastAPI webhook/polling, Tortoise (опц.), Pydantic AI (опц.)
- worker: Prefect flows + tasks, prefect.yaml, docker-compose worker profile
1. Создай docs/spec/stack.md с полным списком (default + choices).
2. edit docs/spec/meta.md frontmatter: phase=2.
3. spec_status валидирует mandatory items через содержимое stack.md — если FAIL, верни что не хватает.
4. Верни: "done: stack.md created, <N>/<M> mandatory items".
```

### Template D (modules / Phase 3, с memory_search)

```
Контекст: Phase 3 (modules) для проекта типа <type>.
Ответ юзера: <answers>.
1. memory_search("reference repo <module>") — доберёт паттерны из mediakit/digital_factory/etc.
2. Сформируй ## Модули (bullet list) + ## Структура (дерево) на основе ответа + референсов.
3. Создай docs/spec/modules.md с обеими секциями. edit docs/spec/meta.md frontmatter phase=3.
4. Верни summary (5-10 строк) для показа юзеру.
```

### Template E (db_schema / Phase 4)

```
Обнови docs/spec для Phase 4 (DB_SCHEMA).
Ответы юзера: <answers> (или "no_db" если выбрано).
1. Если no_db: edit docs/spec/meta.md frontmatter no_db=true (db-schema.md НЕ создаётся).
2. Иначе: создай docs/spec/db-schema.md со сущностями из ответа.
3. edit docs/spec/meta.md frontmatter phase=4.
4. Верни: "done: db-schema updated".
```

### Template F (infra / Phase 5)

```
Обнови docs/spec для Phase 5 (INFRA).
Ответы юзера: <answers>.
1. Создай docs/spec/infra.md.
2. edit docs/spec/meta.md frontmatter phase=5.
3. Верни: "done: infra.md updated".
```

### Template G (roadmap / Phase 6)

```
Обнови docs/spec для Phase 6 (ROADMAP).
Ответы юзера: <answers>.
1. Создай docs/spec/roadmap.md с N пунктами.
2. edit docs/spec/meta.md frontmatter phase=6.
3. Верни: "done: roadmap.md updated, N пунктов".
```

### Template H (confirm / Phase 7)

```
Прочитай все файлы docs/spec/*.md (meta.md, context.md, stack.md, modules.md, db-schema.md если есть, infra.md, roadmap.md).
1. edit docs/spec/meta.md frontmatter confirmed=true, phase=7 (если юзер подтвердил).
2. Верни полный текст spec (все файлы конкатенированные) для показа юзеру.
```

### Template I (execute / Phase 8, create issues)

```
Создай N GitHub issues по roadmap из docs/spec/roadmap.md.

1. Load `issue` skill via `skill({name: "issue"})`.
2. Прочитай docs/spec/stack.md, docs/spec/modules.md, docs/spec/db-schema.md (если есть), docs/spec/infra.md для контекста.
3. Для каждого пункта roadmap (по порядку):
   - Сформируй самодостаточный issue body (issue-skill format):
     ## Контекст
     ## Что сделать (пошагово с путями к файлам)
     ## Проверка (команды)
     ## Связанные ресурсы (Part of spec, ref к docs/spec/roadmap.md)
   - Issue #1 (scaffolding) body ДОЛЖЕН включать:
     "Используй repo-init skill для: pyproject.toml, CI, .gitignore, LICENSE, dependabot, pre-commit. Структура — из ## Структура в docs/spec/modules.md."
   - gh issue create --title "type(scope): description" --body "<body>" --label "enhancement,from-spec"
4. Собери реальные номера issues из вывода gh.
5. Update docs/spec/roadmap.md: добавь реальные #N номера. Update docs/spec/meta.md: executed=true, phase=8.
6. Верни: [{number, url, title}, ...] для всех issues.
```

## Rules

- `spec_status` — единственный source of truth для порядка шагов и действий.
- Скрипт read-only (только presence check в `docs/spec/*.md`, без мутаций).
- После каждой фазы → 1 строка прогресса юзеру.
- Если subagent error → 1 retry, потом STOP + report пользователю.
- Главный агент = оркестратор: `spec_status` tool + вопрос юзеру + task(general) делегирование. Не делает edit/memory_search/gh сам.
- Стоп на issues — дальше юзер сам /pipeline-driver.