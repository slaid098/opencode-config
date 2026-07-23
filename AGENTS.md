# Global Rules

## Orchestrator Model (главное)

- Главный чат = ТОЛЬКО план. Все исследования, команды, edits, реализации — ТОЛЬКО через subagents.
- Никогда не делать самому: research файловой системы, grep/glob, bash-команды, file edits, тесты, git ops.
- Максимум: верхнеуровневый план + отчёты пользователю + делегирование `task` subagent'ам.
- Pipeline: каждую фазу (ISSUE → IMPLEMENT → DOCS → CI → REVIEW → MERGE → MEMORY) делегировать subagent'у.
- Subagent error → 1 retry, потом STOP + report.

## Commits

- Language: English only — type, scope, and description all in English
- Format: `type(scope): description` — ≤72 chars
- Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`
- Before ANY commit: load `commit` skill (`skill("commit")`), run `git log --oneline -20`, match existing style
- Break large changes into multiple short commits by logical parts
- No period at end, no body unless necessary

## Pull Requests

- Title: на английском, формат `type(scope): what changed` — same principle as commits
- Body: на русском, в Markdown — сначала **что** сделано, затем **почему** (мотивация, контекст)
- Reference issues if applicable
- Before creating PR: load `commit` skill, inspect `git diff` from base branch

## Development Workflow

All PR work runs through `/run-pipeline` (7 phases: ISSUE → IMPLEMENT → DOCS → CI → REVIEW → MERGE → MEMORY). Load the `run-pipeline` skill for the protocol.

1. **Plan** — discuss requirements in chat, understand scope
2. **Issue** — create self-contained GitHub issue (full context, file list, exact content, acceptance criteria, dependencies). Load `issue` skill. Via subagent.
3. **Subagent** — delegate to `task` subagent (general type):
   - Reads issue via `gh issue view N`
   - Branches off default branch, implements per spec, commits, pushes, creates PR with `Closes #N`
   - Creates handoff `docs/handoff/pr-<N>-<slug>.md` and ADR if architectural decision
   - Follows issue spec exactly — if spec has errors, report them, don't deviate
4. **Review** — run docs-reviewer (`@docs-reviewer`, pre-merge) then reviewer (`@reviewer`):
   - docs-reviewer: updates project map + validates/fixes handoff + ADR, commits to PR branch
   - reviewer: posts `## Code Review Summary` comment with verdict APPROVE|REQUEST_CHANGES (does NOT merge)
5. **Merge or Repeat**:
   - APPROVE → `merge_pr` tool (orchestrator-safe, via `run-pipeline` skill, after CI ✅)
   - Issues found → fix subagent (same branch, new commit) → re-loop → merge
   - REQUEST_CHANGES → fix subagent → re-review → merge
6. **Memory-sync** — run memory-syncer (`@memory-syncer`):
   - Distills gotchas + ADR pointers from merged handoff into `app_data/opencode-memory/repos/{host}/{org}/{repo}.md`
   - Format: `- [YYYY-MM-DD, PR#N] <summary>`, receipt always (even if empty)
   - Calls `memory_save`, then guards against accidental commits to main repo

## Pipeline

Основной pipeline для любой задачи — `/run-pipeline` в UI opencode. Skill выполняет 7 фаз (ISSUE → IMPLEMENT → DOCS → CI → REVIEW → MERGE → MEMORY) автономно, не импровизируя порядок. `merge_pr` tool — после CI ✅ (transitive guard в `pipeline-status.py`).

- Tool `pipeline_status` — read-only oracle, возвращает статус + NEXT action.
- Tool `merge_pr` — orchestrator-safe merge wrapper (replaces raw `gh pr merge`).
- Execution — через `/run-pipeline` (command `.opencode/commands/run-pipeline.md`).

## Read Path

Перед началом задачи в репо: просмотри имена файлов в `docs/handoff/` (если есть) — открой релевантные по теме.

## Code Style

- Follow existing conventions in the repo
- Load `code-standards` skill for detailed rules
- No comments unless explicitly requested
- Match surrounding code style (imports, naming, patterns)

## Language

- Always respond to the user in Russian.