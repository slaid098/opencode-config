---
name: configure-opencode
description: Use when adding, changing, or removing MCP servers, providers, permissions, agents, plugins, or any block in opencode.json. Always writes to .opencode/opencode.json in slaid098/opencode-config (project-local, auto-discovered, zero env var). Also when user says "добавь MCP", "подключи интеграцию", "пропиши permissions", "добавь провайдера", "измени конфиг opencode", "куда писать конфиг".
---

# configure-opencode

Канонический скилл для правок `opencode.json` в репо `slaid098/opencode-config`. Фиксирует контракт «куда писать конфиг» и форматы блоков. Конфиг-репо — это шаблон, который клонируют пользователи.

## 1. Каноническое правило (canonical rule)

- **Всегда** пишем конфиг в `.opencode/opencode.json` в репо `slaid098/opencode-config` (project-local, auto-discovered). opencode автоматически подхватывает `.opencode/opencode.json` при запуске — без env var, без bind-mount, без symlink.
- **Репо `slaid098/opencode-config` сам по себе — шаблон**, который пользователь клонирует: `git clone … && opencode` в корне клона — и конфиг работает.
- **НЕ создавать** отдельный project-local `opencode.json` в других репо (например `.opencode/opencode.json` в `other-repo`) для глобальных настроек. Глобальные правки идут в `slaid098/opencode-config`.
- **НЕ спрашивать** пользователя «куда писать конфиг» — ответ всегда `.opencode/opencode.json` в `slaid098/opencode-config`.
- **Исключение:** явный override-сценарий (project-local конфиг нужен для изоляции в конкретном проекте) — тогда указать явно в комментарии к изменению.
- **Docker (опционально):** для контейнерного запуска можно bind-mount `.opencode/` → `~/.config/opencode/` (см. `docker-compose.yml`) — но это optional path, не канон. Репо обязан работать и bare-`opencode` в клона.

## 2. Применение изменений

- `commit` + `push` в репо `slaid098/opencode-config` (через `commit` skill).
- В клонах: `git pull` + рестарт opencode (MCP-серверы, skills, agents грузятся при старте — см. `add-skill/SKILL.md`). До рестарта правки не видны.
- Для Docker-сетапа: `git pull` на хосте + `docker compose restart opencode` (или эквивалент) — MCP/skills/agents грузятся при старте контейнера.

## 3. Структура top-level ключей `opencode.json`

- `$schema` — JSON-schema URL для автокомплита в IDE.
- `plugin` — npm-пакет плагина (например `@mathew-cf/opencode-memory`).
- `skills.paths` — массив путей к skill-директориям (по умолчанию `[".opencode/skills"]`).
- `compaction` — настройки сжатия контекста.
- `disabled_providers` — массив отключённых провайдеров.
- `provider` — current provider config (см. ниже).
- `permission` — permission rules (read/bash, см. ниже).
- `agent` — per-agent overrides (frontmatter-like, переопределяет per-agent).
- `mcp` — MCP-серверы (remote/local, см. ниже).

## 4. MCP-форматы

**Remote (streamable-HTTP):**

```json
"<name>": {
  "type": "remote",
  "url": "https://example.com/mcp",
  "enabled": true,
  "timeout": 300000
}
```

**Local (subprocess):**

```json
"<name>": {
  "type": "local",
  "command": ["npx", "-y", "<package>"],
  "enabled": true
}
```

**Env-плейсхолдеры:** `"{env:VAR_NAME}"` — значение подставляется из env. **НЕ хардкодить** секреты (API keys, tokens) в JSON. Пример: `"url": "{env:MY_API_URL}"`, `"--api-key", "{env:MY_API_KEY}"`.

**timeout** — в миллисекундах, обязателен для медленных MCP (LLM-агенты, скрапинг). Для быстрых (well-known manifests) — можно опустить (default).

## 5. Provider-формат

```json
"provider": {
  "npm": "<package-name>",
  "options": {
    "baseURL": "https://api.example.com/v1",
    "apiKey": "{env:PROVIDER_API_KEY}"
  },
  "models": {
    "<model-id>": {
      "limit": { "context": 128000, "output": 8192 },
      "reasoning": true,
      "modalities": ["text", "image"],
      "variants": ["<variant-id>"]
    }
  }
}
```

## 6. Permissions

- `read` — массив glob-паттернов для разрешённых read-путей (например `["**/*"]` или `["./src/**"]`).
- `bash` — объект `"<pattern>": "<action>"` где:
  - `action` — `"allow"`, `"ask"`, или `"deny"`.
  - `pattern` — glob-паттерн bash-команды (например `"git push*"`, `"gh pr merge*"`, `"python3*"`).
- **Семантика `findLast`:** при нескольких матчах побеждает последнее правило (last wins). Это значит порядок правил имеет значение.
- **Три состояния:**
  - `allow` — команда выполняется без подтверждения.
  - `ask` — opencode спрашивает пользователя перед выполнением.
  - `deny` — команда блокируется (deny-лог в `opencode.log`).
- **Guard:** после правок `permission.bash` запускать локально `python3 .opencode/scripts/check-permissions.py` — детектирует опасные паттерны (например `gh pr checks*`, см. ADR-006). CI (`permissions-check.yml`) запускает тот же скрипт.
- См. ADR-006 (детерминированный guard), ADR-005 (Actions API вместо Checks API в allow-list'ах).

## 7. Gotchas

- **Рестарт обязателен:** правки в `.opencode/opencode.json` НЕ видны opencode до рестарта (MCP/skills/agents грузятся при старте). В клонах — рестарт opencode; в Docker — `docker compose restart opencode`.
- **env-плейсхолдеры не хардкод:** секреты в `.env` (не в git), плейсхолдер `"{env:VAR}"` в `opencode.json` (в git). Пример: `MY_API_URL`, `MY_API_KEY`, `MY_TUNNEL_TOKEN`.
- **`OPENCODE_CONFIG_DIR` env var (power-user/Docker):** указывает на директорию с `opencode.json` — загружается ПОСЛЕ `.opencode/` и МОЖЕТ переопределять его. Канонический путь `.opencode/` не требует этого env var; `OPENCODE_CONFIG_DIR` нужен только для кастомного layout (Docker, power-user).
- **`findLast` семантика:** при конфликте правил побеждает последнее. Если добавить `deny` после `allow` — `deny` wins. Если `allow` после `deny` — `allow` wins. Порядок имеет значение.
- **CI проверяет permissions:** `permissions-check.yml` запускается на PR с изменениями `.opencode/opencode.json`, `.opencode/agents/**`, `.opencode/scripts/check-permissions.py`. Локальная проверка перед commit: `python3 .opencode/scripts/check-permissions.py` → exit 0, "OK: No dangerous permission rules found."

## 8. Commit message

- Формат: `feat(config): ...` / `chore(config): ...` / `fix(config): ...` (conventional commits, English, ≤72 chars).
- Перед commit — загрузить `commit` skill, проверить `git log --oneline -20`, match existing style.
- Примеры: `feat(config): add integrations MCP server`, `fix(config): correct timeout for integrations discover tool`.

## 9. Не дублировать блоки между репо

- `.opencode/opencode.json` в `slaid098/opencode-config` — единственный источник правды для конфига. Репо сам по себе — шаблон, который клонируют.
- Project-local `opencode.json` в других репо — только для явного override (например отключить MCP для конкретного проекта). В 99% случаев не нужен — клонируй `slaid098/opencode-config` или используй `instructions` array с remote URLs.