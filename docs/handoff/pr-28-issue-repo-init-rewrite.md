# PR: issue + repo-init skills rewrite

## Что сделано
- issue skill: full subagent delegation model (main agent передаёт intent summary → subagent грузит skill, читает файлы, пишет body, запускает `gh issue create`), добавлены секции `## Acceptance criteria` (явный чек-лист) и `## Dependencies` (Blocked by / Do not merge until / Part of) в шаблон и пример, исправлен stale workflow (добавлены docs-reviewer + memory-sync шаги, теперь 5 шагов вместо 3), "репозитории opencode" → "репозитории opencode-config", добавлен guidance по выбору labels
- repo-init skill: переписано description (нет ambiguous "or"), добавлен Phase A / Phase B split (Phase A — GitHub remote steps 1-3, Phase B — project scaffolding steps 4-9), добавлен prerequisite `git init` + initial commit перед Step 1, убраны private-repo references (video_uniq, yt-video-downloader, opencode-voice-dictation, slaid098-dev → generic "reference repos", "Эталон — video_uniq" removed)

## Почему
issue skill имел 3-way contradiction на delegation: `issue/SKILL.md` (main agent writes body, subagent runs gh) vs `pipeline-driver/SKILL.md` ("через subagent с issue skill") vs `AGENTS.md` Dev Workflow (subagent не упомянут). repo-init skill имел ambiguous "or" в description, missing `git init` prerequisite (bare-repo → empty push → branch protection fail), private-repo references (не релевантны публичному шаблону).

## Pending
- Нет

## Watch out
- issue skill: 3 документа (`issue/SKILL.md`, `pipeline-driver/SKILL.md`, `AGENTS.md` Dev Workflow) теперь описывают одну full-subagent модель делегирования. `AGENTS.md` Dev Workflow step 2 уже упоминал "delegate to `task` subagent" — консистентно без правок AGENTS.md
- repo-init skill: Phase A/B split позволяет jump к Phase B для scaffolding-only (существующий репо). Phase A — run once для нового репо
- `--label "enhancement"` заменён на guidance по выбору label по commit `type` (enhancement/bug/refactor/documentation/chore/performance) + примечание про `gh label create` если label не существует
- Verification greps (issue #13): `subagent` ✓, `Acceptance criteria` ✓, `Dependencies` ✓, private refs ✓ пусто, `or initializing` ✓ пусто