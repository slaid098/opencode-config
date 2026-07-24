import { spawnSync } from "child_process"
import { tool } from "@opencode-ai/plugin"

const TITLE_REGEX = /^(feat|fix|chore|docs|refactor|test|style|perf)\([^)]+\): .{1,80}$/
const CYRILLIC = /[\u0400-\u04FF]/

const RULES = `Rules:
- Title: type(scope): description (<=80 chars description)
- Types: feat, fix, chore, docs, refactor, test, style, perf
- Scope is mandatory
- Title in English only
- Body must contain '## Контекст' heading
- Body must contain '## Задача' heading
- Body must contain '## Критерии приемки' heading
- Body in Russian (must contain Cyrillic)`

export default tool({
  description: "Create a GitHub issue with title/body validation. Validates: title format type(scope): description (<=80), English title, body headings (## Контекст, ## Задача, ## Критерии приемки), body in Russian. Optional labels. Returns issue URL on success.",
  args: {
    title: tool.schema.string().describe("Issue title (conventional format: type(scope): description, <=80 chars)"),
    body: tool.schema.string().describe("Issue body in Russian with ## Контекст, ## Задача, ## Критерии приемки headings"),
    labels: tool.schema.array(tool.schema.string()).optional().describe("Labels to assign (e.g. ['bug', 'enhancement'])"),
  },
  async execute(args, context) {
    const title = args.title
    const body = args.body

    if (!TITLE_REGEX.test(title)) {
      return `❌ Issue title must match format: type(scope): description\n\n${RULES}`
    }
    if (CYRILLIC.test(title)) {
      return `❌ Issue title must be in English\n\n${RULES}`
    }
    if (!body.includes("## Контекст")) {
      return `❌ Issue body must contain '## Контекст' heading\n\n${RULES}`
    }
    if (!body.includes("## Задача")) {
      return `❌ Issue body must contain '## Задача' heading\n\n${RULES}`
    }
    if (!body.includes("## Критерии приемки")) {
      return `❌ Issue body must contain '## Критерии приемки' heading\n\n${RULES}`
    }
    if (!CYRILLIC.test(body)) {
      return `❌ Issue body must be in Russian\n\n${RULES}`
    }

    const ghArgs = ["issue", "create", "--title", title, "--body", body]
    if (args.labels && args.labels.length > 0) {
      ghArgs.push("--label", args.labels.join(","))
    }

    const r = spawnSync("gh", ghArgs, {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ gh issue create failed (exit ${r.status}): ${r.stderr || r.stdout}`
    }

    return `Issue created: ${r.stdout.trim()}`
  },
})