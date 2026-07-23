---
name: issue
description: Создаёт GitHub issue. Issue должны быть самодостаточными — агент в пустом чате может выполнить без доп. контекста. Если задача большая — разбей на несколько маленьких. Используй subagent для создания чтобы не засорять контекст. Also when user says "создай ишью", "создай issue", "заведи задачу", "разбей на подзадачи", "create issue".
---

## Принцип: один issue = один PR

Issue — это атомарная задача, выполнимая за один PR. Если задача касается > 3-5 файлов или содержит независимые изменения → разбей на несколько issue. Каждый под-issue связывается с родительским через `Part of #N`. Родительский issue закрывается только когда все под-issue смержены.

## Самодостаточность issue

Issue должно содержать всё необходимое, чтобы агент в пустом чате (без контекста предыдущей беседы) мог выполнить задачу:

- **Пути к файлам** — конкретные, с номерами строк если применимо (например `src/video_uniq/effects/camera.py:72`)
- **Что менять** — точное описание изменений, не абстрактное «улучшить» или «починить»
- **Примеры из кода** — если нужно показать паттерн, сослаться на конкретный файл и строки
- **Команды проверки** — какие команды запустить после изменений (pytest, ruff, mypy) и какой ожидаемый результат
- **Связанные ресурсы** — ссылки на связанные issue/PR (например `Ref #33`, `Closes #33`)

## Структура body

```markdown
## Контекст
(зачем это нужно, какая проблема решается)

## Что сделать
(пошагово, с путями к файлам)

### Шаг 1: ...
- Файл: `path/to/file.py`
- Изменить: ...

### Шаг 2: ...

## Проверка
(команды и ожидаемый результат)
- `pytest tests/test_xxx.py -x -q --no-cov` → all passed
- `ruff check path/to/file.py` → All checks passed
- `mypy path/to/file.py` → no issues

## Acceptance criteria
(явный чек-лист — что должно быть верно в результате, не команды проверки)
- [ ] Эффект A работает в случае B
- [ ] Файл C не содержит паттерн D
- [ ] Тест E покрывает ветку F
- [ ] Coverage ≥ 80% на изменённых файлах

## Dependencies
(связи с другими issue/PR — блокировки и порядок)
- Blocked by #N (этот PR нельзя начать пока #N не смержен)
- Do not merge until #N merges (этот PR готов, но ждёт #N)
- Part of #N (подзадача родительского issue)

## Связанные ресурсы
- Ref #33
- [PR #34](https://github.com/...)
```

## Правило дробления

Перед созданием issue оцени объём:

- 1-3 файлов → один issue
- > 3-5 файлов или несколько независимых изменений → предложи пользователю разбить на несколько issue
- Каждый под-issue самодостаточен (свой контекст, свои пути, своя проверка)
- Связь через `Part of #N` (подзадача) и `Closes #N` (когда подзадача закрывает родительскую)

Пример:

> Пользователь: «Перепиши логику рендеринга, добавь кэширование и почини баг с памятью»
> Агент: «Это 3 независимые задачи. Создам 3 issue: #10 (рендеринг), #11 (кэширование), #12 (баг памяти). Каждый выполним одним PR.»

## Использование subagent для создания issue

Issue создаёт **subagent** (general type), а не основной агент. Это сохраняет контекст основного агента — длинный body issue не попадает в его историю.

**Main agent** передаёт subagent'у только **intent summary** — короткое описание задачи (1-3 предложения: что и зачем). Subagent делает всё остальное.

**Subagent (полная ответственность):**
1. Загрузи навык `issue`
2. Собери контекст — прочитай файлы из intent summary, пойми задачу, оцени объём (правило дробления ниже)
3. Составь self-contained body по шаблону (Контекст → Что сделать → Проверка → Acceptance criteria → Dependencies → Связанные ресурсы)
4. Запусти `gh issue create --title "..." --body "..."` (labels — см. guidance ниже)
5. Верни URL созданного issue основному агенту

Main agent НЕ пишет body и НЕ запускает `gh issue create` — всё через subagent. Это согласовано с `pipeline-driver` skill (Phase 0: "через subagent с `issue` skill") и `AGENTS.md` (Dev Workflow, step 2: "delegate to `task` subagent").

## Пример хорошего issue

```markdown
## Контекст
Zoom breathing падает при включённом geometry crop — crop использует probe.width вместо iw.

## Что сделать
### Шаг 1: Заменить probe dimensions на iw/ih выражения
- Файл: `src/video_uniq/effects/camera.py:72`
- Заменить `w, h = probe.width, probe.height` на `iw`/`ih` выражения

## Проверка
- `pytest tests/test_effects.py -x -q --no-cov` → all passed
- `pytest tests/test_new_effects_real.py::test_geometry_crop_with_zoom_breathing_real` → passed

## Acceptance criteria
- [ ] Geometry crop использует `iw`/`ih`, не `probe.width`/`probe.height`
- [ ] Zoom breathing не падает при включённом geometry crop
- [ ] Регрессионный тест покрывает комбинацию zoom breathing + geometry crop

## Dependencies
- Closes #33

## Связанные ресурсы
- Closes #33
```

## Пример плохого issue

```markdown
**Зачем:** нужно улучшить обработку видео
**Что сделать:** переписать эффекты чтобы не падали
```

Почему плохо: нет путей к файлам, нет конкретных шагов, нет команд проверки, абстрактное описание.

## Команда создания

```bash
gh issue create \
  --title "type(scope): description" \
  --body "..." \
  --label "<label>"
```

Label выбирай по типу задачи (совпадает с commit `type`):
- `enhancement` — новая функциональность (`feat`)
- `bug` — исправление (`fix`)
- `refactor` — рефакторинг без изменения поведения (`refactor`)
- `documentation` — доки (`docs`)
- `chore` — обслуживание, зависимости, конфиг (`chore`)
- `performance` — производительность (`perf`)

Если label не существует в репо — `gh issue create` упадёт. Создай через `gh label create <name> --color <hex>` (один раз) или опусти `--label`.

## Пути навыков

Навыки создаются в `.opencode/skills/` в репозитории opencode-config. НЕ в `~/.config/opencode/skills/` — это маунт из репо. После изменения навыка нужен `git pull` на хосте + рестарт opencode.

## Полный workflow

После создания issue, цикл продолжается (см. `pipeline-driver` skill для деталей PR процесса):

1. **Subagent** — `task(general)` читает issue, реализует, коммитит, push, создаёт PR. Оркестрация — через `pipeline-driver` skill.
2. **Docs review** — `@docs-reviewer` subagent валидирует handoff + ADR, обновляет project map (pre-merge).
3. **Code review** — `@reviewer` subagent ревьюит PR (diff, skills, standards), постит `## Code Review Summary` комментарий.
4. **Merge or Repeat** — APPROVE → `gh pr merge N --squash --delete-branch` (после CI ✅); замечания → fix subagent → re-review → merge.
5. **Memory-sync** — `@memory-syncer` дистиллирует handoff + ADR в `app_data/opencode-memory/repos/{host}/{org}/{repo}.md`.

См. `AGENTS.md` (Development Workflow) и `pipeline-driver` skill — все три документа описывают одну и ту же full-subagent модель делегирования.