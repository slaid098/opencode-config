---
name: add-skill
description: Use when creating a new opencode skill. Covers file location, frontmatter format, commit, push, and post-instructions for restart. Also when user says "добавь скилл", "создай скилл", "новый навык".
---

# Add Skill

Процесс создания нового скилла в opencode.

## 1. Куда создавать

```
.opencode/skills/<skill-name>/SKILL.md
```

В корне текущего репо (`<repo-root>` = `git rev-parse --show-toplevel`),
в `.opencode/skills/`. НЕ в `~/.config/opencode/` — эта папка синхронизируется из репо.

## 2. Формат SKILL.md

```markdown
---
name: <skill-name>
description: <когда загружать. Триггеры на русском и английском. Например: Use when ... Also when user says "...">
---

# Skill Title

Содержание скилла.
```

### Правила

- `name` — kebab-case, совпадает с именем директории
- `description` — содержит конкретные триггеры (когда агент должен загрузить этот скилл)
- Язык тела — русский с английскими техническими терминами (как в существующих скиллах)
- Один скилл — одна директория с одним `SKILL.md`

### Примеры существующих скиллов

```
.opencode/skills/
├── add-skill/SKILL.md          ← этот скилл
├── branch/SKILL.md
├── code-standards/SKILL.md
├── commit/SKILL.md
├── get-project-map/SKILL.md
├── issue/SKILL.md
├── memory/SKILL.md
├── pipeline-driver/SKILL.md
├── python-development/SKILL.md
├── repo-init/SKILL.md
├── run-tests/SKILL.md
└── spec-driver/SKILL.md
```

## 3. Скиллы авто-дискаверятся

Opencode сканирует все под-директории `.opencode/skills/` и подхватывает любой `SKILL.md`. Регистрировать ничего не нужно.

Список скиллов загружается **при старте opencode**. Новый скилл станет доступен только после рестарта.

## 4. Commit и Push (для implementing agent)

Implementing agent (subagent, которому делегировано создание) после создания файла — сразу коммит и пуш по правилам скилла `commit`:

```bash
cd "$(git rev-parse --show-toplevel)"
git add .opencode/skills/<skill-name>/SKILL.md
git commit -m "feat(skills): add <skill-name> skill for <purpose>"
git push
```

## 5. Инструкция пользователю

После push сообщить пользователю:

> Скилл создан и запушен. Чтобы он заработал:
> 1. На хосте: `git pull` в репозитории opencode
> 2. Рестарт opencode
>
> После рестарта скилл появится в `available_skills` и будет загружаться по триггерам из `description`.
