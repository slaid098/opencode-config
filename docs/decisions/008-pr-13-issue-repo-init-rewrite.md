# ADR-008: issue + repo-init skills rewrite

## Статус
Accepted

## Контекст
`issue` skill имел 3-way contradiction на delegation model: `issue/SKILL.md` описывал "main agent writes body, subagent runs `gh issue create`" (split responsibility), `pipeline-driver/SKILL.md` Phase 0 говорил "через subagent с `issue` skill" (full subagent), `AGENTS.md` Development Workflow step 2 говорил "delegate to `task` subagent" (subagent, но без уточнения что пишет body). Три документа описывали разные модели → агент не понимал кто пишет body.

`repo-init` skill: ambiguous "or" в description ("creating a new repository or initializing repo settings" — два разных интента в одной фразе), missing `git init` prerequisite перед `gh repo create --source=.` (bare-repo без initial commit → empty push → main branch не появляется → branch protection падает), private-repo references (video_uniq, yt-video-downloader, opencode-voice-dictation, slaid098-dev) не релевантны публичному шаблону.

## Решение
- **issue skill — full subagent delegation:** main agent передаёт только intent summary (1-3 предложения), subagent грузит `issue` skill, читает файлы, пишет self-contained body, запускает `gh issue create`. Main agent НЕ пишет body и НЕ запускает gh. Согласовано с `pipeline-driver` Phase 0 и `AGENTS.md` Dev Workflow.
- **issue skill — template sections:** добавлены `## Acceptance criteria` (явный чек-лист результата, не команды проверки) и `## Dependencies` (Blocked by #N / Do not merge until #N / Part of #N). В шаблон и в пример хорошего issue.
- **issue skill — stale workflow:** "Полный workflow" расширен с 3 до 5 шагов (добавлены docs-reviewer и memory-syncer). "репозитории opencode" → "репозитории opencode-config". `--label "enhancement"` → guidance по выбору label по commit `type`.
- **repo-init skill — description rewrite:** "Sequential checklist: create GitHub remote → configure settings/branch protection → scaffold project files (Python/JS). Use when starting a new repo." — без ambiguous "or".
- **repo-init skill — Phase A/B split:** Phase A (GitHub remote, steps 1-3, run once), Phase B (project scaffolding, steps 4-9, reusable). Позволяет jump к Phase B для существующего репо.
- **repo-init skill — git init prerequisite:** добавлен Step 0 (`git init` + initial commit) перед `gh repo create --source=.`.
- **repo-init skill — remove private refs:** private-repo names → generic "reference repos", "Эталон — video_uniq" removed.

## Альтернативы
- **Drop issue skill (use raw `gh`)** — отклонено: template (Контекст → Что сделать → Проверка → Acceptance criteria → Dependencies) и правило дробления ценны; без skill агенты пишут abstract issues без путей к файлам.
- **Split repo-init into repo-create + repo-init skills** — отклонено: Phase A (create) слишком тонкая для отдельного skill (3 шага); Phase A/B split внутри одного skill даёт нужную гибкость без увеличения skill count.
- **Править `AGENTS.md` Dev Workflow** — отклонено: step 2 уже говорил "delegate to `task` subagent" — консистентно с full-subagent моделью без правок.