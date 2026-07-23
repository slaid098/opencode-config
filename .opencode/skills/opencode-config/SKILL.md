---
name: opencode-config
description: Use when adding, changing, or removing MCP servers, providers, permissions, agents, plugins, or any block in opencode.json. Always writes to config/opencode.json in slaid098/opencode-config repo (bind-mounted to global ~/.config/opencode/). Also when user says "добавь MCP", "подключи интеграцию", "пропиши permissions", "добавь провайдера", "измени конфиг opencode", "куда писать конфиг".
---

# opencode-config

Канонический скилл для правок `opencode.json` в репо `slaid098/opencode-config`. Фиксирует контракт «куда писать конфиг» и форматы блоков.

## 1. Каноническое правило (canonical rule)

- **Всегда** пишем конфиг в `config/opencode.json` в репо `slaid098/opencode-config` → bind-mount `./config:/root/.config/opencode` (docker-compose.yml) → global `/root/.config/opencode/opencode.json`.
- **НЕ создавать** project-local `opencode.json` в других репо (например `.opencode/opencode.json` в `other-repo`).
- **НЕ спрашивать** пользователя «куда писать конфиг» — ответ всегда `config/opencode.json` в `slaid098/opencode-config`.
- **Исключение:** явный override-сценарий (project-local конфиг нужен для изоляции) — тогда указать явно в комментарии к изменению.

Memory: `technical/opencode-config-global-vs-local.md` — детально описывает механизм bind-mount.

## 2. Применение изменений

- `commit` + `push` в репо `slaid098/opencode-config` (через `commit` skill).
- На хосте: `git pull` в корне репо `slaid098/opencode-config`.
- Рестарт контейнера: MCP-серверы, skills, agents грузятся при старте (см. `add-skill/SKILL.md`, ADR-013). До рестарта правки не видны.
- Для Windows bare-metal (`windows/start.bat`): см. ADR-009 — `OPENCODE_CONFIG_DIR` НЕ выставляется (LSP-конфликт с `pyproject.toml` в cwd), конфиг на винде — отдельная задача.

## 3. Структура top-level ключей `opencode.json`

- `$schema` — JSON-schema URL для автокомплита в IDE.
- `plugin` — npm-пакет плагина (например `@mathew-cf/opencode-memory`).
- `skills.paths` — массив путей к skill-директориям (по умолчанию `[".opencode/skills"]`, global из bind-mount добавляется автоматически).
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

**Env-плейсхолдеры:** `"{env:VAR_NAME}"` — значение подставляется из env контейнера. **НЕ хардкодить** секреты (API keys, tokens) в JSON. Пример: `"url": "{env:ANTIDETECT_BROWSER_MCP_URL}"`, `"--api-key", "{env:CONTEX7_API_KEY}"`.

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
- **Guard:** после правок `permission.bash` запускать локально `python3 config/scripts/check-permissions.py` — детектирует опасные паттерны (например `gh pr checks*`, ADR-006). CI (`permissions-check.yml`) запускает тот же скрипт.
- См. ADR-006 (детерминированный guard), ADR-005 (Actions API вместо Checks API в allow-list'ах).

## 7. Gotchas

- **bind-mount требует рестарта:** правки в `config/opencode.json` НЕ видны opencode до рестарта контейнера (MCP/skills/agents грузятся при старте). После commit+push — `git pull` на хосте + `docker compose restart opencode` (или эквивалент).
- **env-плейсхолдеры не хардкод:** секреты в `.env` (не в git), плейсхолдер `"{env:VAR}"` в `opencode.json` (в git). Пример: `ANTIDETECT_BROWSER_MCP_URL`, `CONTEX7_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`.
- **`OPENCODE_CONFIG_DIR` env var:** указывает на директорию с `opencode.json`. На сервере задаётся `docker-compose.yml:environment`, на Windows bare-metal НЕ выставляется (ADR-009 — LSP-конфликт с `pyproject.toml` в cwd).
- **`findLast` семантика:** при конфликте правил побеждает последнее. Если добавить `deny` после `allow` — `deny` wins. Если `allow` после `deny` — `allow` wins. Порядок имеет значение.
- **CI проверяет permissions:** `permissions-check.yml` запускается на PR с изменениями `config/opencode.json`, `config/agents/**`, `config/scripts/check-permissions.py`. Локальная проверка перед commit: `python3 config/scripts/check-permissions.py` → exit 0, "OK: No dangerous permission rules found."

## 8. Commit message

- Формат: `feat(config): ...` / `chore(config): ...` / `fix(config): ...` (conventional commits, English, ≤72 chars).
- Перед commit — загрузить `commit` skill, проверить `git log --oneline -20`, match existing style.
- Примеры: `feat(config): add integrations.sh MCP server`, `fix(config): correct timeout for integrations discover tool`.

## 9. Не дублировать блоки между репо

- `opencode.json` в `slaid098/opencode-config` — единственный источник правды для global-конфига.
- Project-local `opencode.json` в других репо — только для явного override (например отключить MCP для конкретного проекта). В 99% случаев не нужен.