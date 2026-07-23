# PR: opencode-config skill rewrite + rename /configure-opencode

## Что сделано
- Rename: /opencode-config → /configure-opencode (command file + skill dir + `skill({name: ...})` ref)
- Rewrite canonical rule: `config/opencode.json` + bind-mount → `.opencode/opencode.json` (project-local, auto-discovered, zero env var). Репо сам — шаблон, который клонируют.
- Dropped: bind-mount как primary механизм (→ optional Docker path), `OPENCODE_CONFIG_DIR` как required concept (→ power-user/Docker env var only), Windows bare-metal / `windows/start.bat` (LSP-конфликт `pyproject.toml` на Windows — не релевантен публичному Linux-шаблону), internal env vars (`ANTIDETECT_BROWSER_MCP_URL`, `CONTEX7_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`) → generic `{env:MY_API_KEY}`
- Renamed paths: `config/...` → `.opencode/...` (включая `check-permissions.py` guard ref), `slaid098/opencode` → `slaid098/opencode-config` (кроме `opencode-memory`)
- Preserved: форматы MCP/provider/permission, top-level keys reference, `findLast` semantic, `check-permissions.py` guard, ADR-005/ADR-006 refs
- Side: `docs/project-map/README.md` — обновлены строки `opencode-config.md` → `configure-opencode.md`, `opencode-config/SKILL.md` → `configure-opencode/SKILL.md` (минимально, чтобы не оставлять битые refs после rename)

## Почему
Skill описывал старую архитектуру (`config/opencode.json` + bind-mount + `OPENCODE_CONFIG_DIR` + Windows bare-metal). Новый репо использует `.opencode/` auto-discovery (см. ADR-002 — миграция config/ → .opencode/). Форматы MCP/provider/permission архитектурно-агностичны — сохранены.

## Pending
- Нет

## Watch out
- Форматы MCP/provider/permission сохранены (архитектурно-агностичны) — правки только в canonical rule (§1, §9), gotchas (§7), paths
- `OPENCODE_CONFIG_DIR` оставлен как power-user/Docker опция (не удалён полностью) — загружается ПОСЛЕ `.opencode/`, может переопределять; канонический путь `.opencode/` не требует его
- `bind-mount` оставлен как optional Docker path (см. `docker-compose.yml`) — репо обязан работать и bare-`opencode` в клона
- Skill `opencode-config` (создан в приватном репо) — superseded этим rewrite. ADR-002 (этого репо) фиксирует миграцию архитектуры `config/` → `.opencode/`
- `docs/project-map/README.md` правки вне issue scope, но без них rename оставил бы битые refs в project map
- ADR refs в SKILL.md (`ADR-005`, `ADR-006`) валидируются `check-adr-refs.py` — `.opencode/` исключён из сканирования, но ADR-005/006 существуют в `docs/decisions/` (если сканирование расширят)