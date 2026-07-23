# PR: Skills minor cleanup batch

## Что сделано
- code-standards: comments rule clarified (no comments = default, public-API docstrings = exception)
- branch: "from main" → "from default branch"
- memory: path inconsistency fixed (plugin default + OPENCODE_MEMORY_DIR override)
- add-skill: config/skills → .opencode/skills, tunnel dropped, reframe for subagent
- get-project-map: removed merged: field, fixed ADR naming convention, repomix noted
- spec-driver: ADR-NNN → ADR-026, removed slaid098 default
- commit: docs scope expanded, removed "why не what", aligned git log -20, ≤72, English only
- issue + pipeline-driver: stale config/skills refs fixed (verification-required)

## Почему
После миграции #7 skills содержали устаревшие/противоречивые инструкции. Cleanup для консистентности.

## Pending
- opencode-config skill rewrite (#12) — canonical rule .opencode/
- issue + repo-init rewrite (#13)

## Watch out
- 9 skills modified в одном PR (7 named + 2 stale-ref cleanup for verification)
- code-standards comments rule: не удалили, уточнили (AGENTS.md = default, skill = exception)
- issue/pipeline-driver не входили в named scope, но verification grep требовала config/skills пусто → fixed