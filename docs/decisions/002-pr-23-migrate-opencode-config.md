# ADR-002: Migrate .opencode/ config (project-local auto-discovery)

## Статус

Accepted

## Контекст

Миграция из приватного репо (config/ + bind-mount + OPENCODE_CONFIG_DIR) в публичный (.opencode/ auto-discovery). Старая архитектура: config/ bind-mounted в /root/.config/opencode/. Новая: .opencode/ project-local, auto-discovered, zero env var.

## Решение

- config/* → .opencode/* (agents, commands, skills, tools, scripts, opencode.json, package.json, .gitignore)
- Исключено: AGENTS.md (#10), personal-knowledge (DROP), tunnel (excluded), ssh/ (private)
- Rename slaid098/opencode → slaid098/opencode-config
- Очищены упоминания внутренних проектов (digital_factory, mediakit, media-gen) → generic examples

## Альтернативы

- Сохранить config/ + bind-mount — отклонено (LSP-конфликт pyproject.toml, не zero-config)
- Дропнуть skills (использовать только глобальные) — отклонено (skills нужны в репо для публичного shareable config)
