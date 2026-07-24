import { spawnSync } from "child_process"
import { tool } from "@opencode-ai/plugin"

const TITLE_REGEX = /^(feat|fix|chore|docs|refactor|test|style|perf)\([^)]+\): .{1,72}$/
const CYRILLIC = /[\u0400-\u04FF]/

const RULES = `Rules:
- Title: type(scope): description (<=72 chars description)
- Types: feat, fix, chore, docs, refactor, test, style, perf
- Scope is mandatory
- Title in English only
- Body must contain '## Что сделано' heading
- Body must contain '## Почему' heading
- Body in Russian (must contain Cyrillic)`

export default tool({
  description: "Create a GitHub PR with title/body validation. Validates: title format type(scope): description (<=72), English title, body headings (## Что сделано, ## Почему), body in Russian. If issue_number provided, appends 'Closes #N' to body. Returns PR URL on success.",
  args: {
    title: tool.schema.string().describe("PR title (conventional format: type(scope): description)"),
    body: tool.schema.string().describe("PR body in Russian with ## Что сделано and ## Почему headings"),
    issue_number: tool.schema.number().optional().describe("Issue number to link (appends 'Closes #N' to body)"),
  },
  async execute(args, context) {
    const title = args.title
    let body = args.body

    if (!TITLE_REGEX.test(title)) {
      return `❌ PR title must match format: type(scope): description\n\n${RULES}`
    }
    if (CYRILLIC.test(title)) {
      return `❌ PR title must be in English\n\n${RULES}`
    }
    if (!body.includes("## Что сделано")) {
      return `❌ PR body must contain '## Что сделано' heading\n\n${RULES}`
    }
    if (!body.includes("## Почему")) {
      return `❌ PR body must contain '## Почему' heading\n\n${RULES}`
    }
    if (!CYRILLIC.test(body)) {
      return `❌ PR body must be in Russian\n\n${RULES}`
    }

    if (args.issue_number) {
      body = body + "\n\nCloses #" + args.issue_number
    }

    const r = spawnSync("gh", ["pr", "create", "--title", title, "--body", body], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ gh pr create failed (exit ${r.status}): ${r.stderr || r.stdout}`
    }

    return `PR created: ${r.stdout.trim()}`
  },
})