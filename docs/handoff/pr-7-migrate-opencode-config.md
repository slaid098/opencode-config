# PR: Migrate .opencode/ config

## Что сделано

- Перенесён global opencode config из `config/` → `.opencode/`:
  - agents/ (3: docs-reviewer, memory-syncer, reviewer)
  - commands/ (3: opencode-config, pipeline-driver, spec-driver)
  - skills/ (14: все кроме tunnel и personal-knowledge)
  - tools/ (2: pipeline-status.ts, spec-status.ts)
  - scripts/ (7: без tunnel.sh)
  - opencode.json, package.json, .gitignore
- Rename slaid098/opencode → slaid098/opencode-config (кроме opencode-memory)
- НЕ перенесено: AGENTS.md (#10), personal-knowledge (DROP), tunnel (excluded), ssh/ (private keys)
- Очищены упоминания внутренних проектов (digital_factory, mediakit, media-gen) → generic examples

## Почему

Миграция из приватного репо в публичный. .opencode/ auto-discovery (project-local, zero env var).

## Pending

- Skills cleanup (#11): minor fixes для 7 skills
- opencode-config skill rewrite (#12): canonical rule .opencode/
- issue + repo-init rewrite (#13): delegation model
- commands rename (#14): /run-pipeline, /spec
- pipeline-driver rewrite (#16): merge_pr tool, config/ paths

## Watch out

- skills count: 14 (16 в config/skills/ минус tunnel минус personal-knowledge)
- tools/ относительные пути `../scripts/` — проверены, работают
- opencode.json может содержать {env:VAR} ссылки — не трогать
- scaffold-handoff.sh теперь в .opencode/scripts/ — следующие PR могут использовать
- add-skill/SKILL.md: tunnel/SKILL.md заменён на spec-driver/SKILL.md в example tree
