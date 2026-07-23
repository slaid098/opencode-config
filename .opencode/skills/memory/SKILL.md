---
name: memory
description: Инструкция по работе с файловой памятью opencode-memory (search + save + retro).
---

# File Memory (opencode-memory)

Графовая память (Graphiti/FalkorDB) удалена — была нестабильна и забагована.
Теперь память работает через `@mathew-cf/opencode-memory` — файловая система с keyword + semantic search.

## Инструменты

| Инструмент | Назначение |
|---|---|
| `memory_search(query, category?)` | Гибридный поиск (keyword + semantic) |
| `memory_list(category?)` | Список категорий / файлов |
| `memory_save()` | Commit + re-index после записи/редактирования |
| `memory_access(path)` | Отметить файл как прочитанный |
| `memory_setup()` | Проверить статус бэкендов |

## Категории

`preferences` · `repos` · `technical` · `people` · `workflows` · `snippets` · `notes`

## Как работать

1. **Перед началом работы** — `memory_search` по теме
2. **В процессе** — сохранять находки сразу (контекст свежий)
3. **В конце сессии** — retrospective: что узнал → сохранить, что было в памяти → обновить, чего не хватало → создать

## Когда сохранять

- gotcha / workaround (неочевидное поведение)
- структура репозитория, команды сборки/тестов
- quirks инструментов
- коренные причины багов (root cause)
- указатели: «для X используй Y, осторожно с Z»

## Когда НЕ сохранять

- данные, которые живой API возвращает свежими каждый раз
- текущий статус тасок / PR / спринтов
- копии вики-страниц и API-документации
- то, что находится за <1 минуты из первых принципов

## Структура файла

```
---
title: Человекочитаемый заголовок
tags: [tag1, tag2]
summary: Описание в одну строку
created: YYYY-MM-DD
updated: YYYY-MM-DD
importance: high | medium | low
source: откуда информация
source_date: YYYY-MM-DD
related: [category/file.md]
---
```

## Путь для репозиториев

Плагинный default: `~/opencode-memory` (переопределяется через `OPENCODE_MEMORY_DIR`, например `app_data/opencode-memory`).

```
{memory-dir}/repos/{host}/{org}/{repo}.md
```

Используй один путь последовательно во всех примерах — default (`~/opencode-memory`) или override (`app_data/opencode-memory`), но не оба сразу.

### Формат записей

```
- [YYYY-MM-DD, PR#N] <суть>
```

Дата и PR-номер в тексте — для RAG-поиска и верификации (какой PR принёс знание).

### Что дистиллировать (durable-only)

- gotchas / workaround (неочевидное поведение)
- паттерны, конвенции репозитория
- указатели: «для X используй Y, осторожно с Z»
- коренные причины багов (root cause)

НЕ дистиллировать: статусы, «сейчас делаем», текущие таски, ephemeral контекст.

### ADR — только указатель

```
- [date, PR#N] ADR-NN: <суть> → docs/decisions/NN-title.md
```

Не копируй содержание ADR — только указатель на файл.

### Править вместо дублирования

Если факт уже записан — обнови запись (bump `updated` в frontmatter). Не создавай дубликаты.

### Квитанция ставится всегда

Даже если durable-записей нет, квитанция обязательна:

```
- [date, PR#N] — (нет durable-записей)
```

Это подтверждает, что memory-sync фаза выполнена (audit trail).
