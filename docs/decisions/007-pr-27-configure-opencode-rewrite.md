# ADR-007: opencode-config skill rewrite for .opencode/ auto-discovery

## Статус
Accepted

## Контекст
`configure-opencode` skill (ранее `opencode-config`, создан в приватном репо) описывал старую архитектуру: `config/opencode.json` + bind-mount + `OPENCODE_CONFIG_DIR` + Windows bare-metal (`windows/start.bat`, LSP-конфликт `pyproject.toml` на Windows — не релевантен публичному Linux-шаблону). Новый репо `slaid098/opencode-config` использует `.opencode/` auto-discovery (project-local, zero env var) — см. ADR-002 (миграция config/ → .opencode/). Skill противоречил ADR-002 и вводил в заблуждение пользователей публичного шаблона.

## Решение
- **Flip canonical rule (§1, §9):** `.opencode/opencode.json` (project-local, auto-discovered) вместо `config/opencode.json` + bind-mount. Репо сам — шаблон, который клонируют (`git clone … && opencode`).
- **Drop:** bind-mount как primary механизм (→ optional Docker path), `OPENCODE_CONFIG_DIR` как required concept (→ power-user/Docker env var only), Windows bare-metal / LSP-конфликт `pyproject.toml` (не мигрировал в публичный репо), internal env vars (`ANTIDETECT_BROWSER_MCP_URL`, `CONTEX7_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`) → generic `{env:MY_API_KEY}`.
- **Rename paths:** `config/...` → `.opencode/...`, `slaid098/opencode` → `slaid098/opencode-config` (кроме `opencode-memory`).
- **Rename command + skill:** `/opencode-config` → `/configure-opencode` (command file, skill dir, `skill({name: ...})` ref, frontmatter `name`).
- **Preserve:** форматы MCP/provider/permission (архитектурно-агностичны), top-level keys reference, `findLast` semantic, `check-permissions.py` guard, ADR-005/ADR-006 refs.

## Альтернативы
- **Drop skill entirely** — отклонено: форматы MCP/provider/permission не очевидны из официальных доков opencode; `findLast` semantic и `check-permissions.py` guard — repo-specific знания, которые нужно сохранить.
- **Keep old skill** — отклонено: противоречит ADR-002 (`.opencode/` architecture), вводит в заблуждение пользователей публичного шаблона (они не используют bind-mount).
- **Rewrite без rename** — отклонено: rename `/opencode-config` → `/configure-opencode` устраняет коллизию имени с репо `slaid098/opencode-config` и лучше отражает action-verb naming остальных commands (`/pipeline-driver`, `/spec-driver`).