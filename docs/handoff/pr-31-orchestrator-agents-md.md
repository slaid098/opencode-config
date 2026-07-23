# PR: Orchestrator AGENTS.md + docker bind-mount

## Что сделано
- Created root AGENTS.md with orchestrator directive (chat = plan only, all via subagents)
- Added docker bind-mount: ./AGENTS.md:/root/.config/opencode/AGENTS.md:ro
- AGENTS.md references /run-pipeline (renamed in #14) and merge_pr tool (created in #16)
- Preserved existing rules: commits, PRs, code style, language (Russian), read path

## Почему
Main agent = pure orchestrator. AGENTS.md in root (committed, auto-loaded for project) + bind-mount makes it global for all projects in container.

## Pending
- Нет (завершающий PR для AGENTS.md)

## Watch out
- AGENTS.md in root = auto-loaded for opencode-config project itself
- bind-mount :ro = read-only in container (source of truth = root file)
- merge_pr tool reference (not raw gh pr merge) — aligns with ADR-010