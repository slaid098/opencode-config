import { spawnSync } from "child_process"
import { tool } from "@opencode-ai/plugin"

const COMMIT_REGEX = /^(feat|fix|chore|docs|refactor|test|style|perf)\([^)]+\): .{1,72}$/
const CYRILLIC = /[\u0400-\u04FF]/

const RULES = `Rules:
- Single-line (no newlines)
- Format: type(scope): description
- Types: feat, fix, chore, docs, refactor, test, style, perf
- Scope is mandatory
- Description: 1-72 characters
- English only (no Cyrillic)`

function recentCommits(worktree) {
  const r = spawnSync("git", ["log", "--oneline", "-5"], {
    encoding: "utf-8",
    cwd: worktree,
  })
  if (r.status !== 0 || !r.stdout.trim()) return "(no commits yet)"
  return r.stdout.trim()
}

export default tool({
  description: "Commit staged files with conventional commit format validation. Validates: single-line, format type(scope): description (<=72 chars description), English only, staged files exist. On error returns rules + recent commits as examples.",
  args: {
    message: tool.schema.string().describe("Commit message (single-line, conventional format: type(scope): description)"),
  },
  async execute(args, context) {
    const msg = args.message

    if (msg.includes("\n")) {
      return `❌ Commit message must be single-line\n\n${RULES}\n\nRecent commits:\n${recentCommits(context.worktree)}`
    }
    if (!COMMIT_REGEX.test(msg)) {
      return `❌ Commit message must match format: type(scope): description\n\n${RULES}\n\nRecent commits:\n${recentCommits(context.worktree)}`
    }
    if (CYRILLIC.test(msg)) {
      return `❌ Commit message must be in English\n\n${RULES}\n\nRecent commits:\n${recentCommits(context.worktree)}`
    }

    const staged = spawnSync("git", ["diff", "--cached", "--name-only"], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (staged.status !== 0) {
      return `⚠️ git diff --cached failed (exit ${staged.status}): ${staged.stderr || staged.stdout}`
    }
    if (!staged.stdout.trim()) {
      return `❌ No staged files to commit\n\n${RULES}\n\nRecent commits:\n${recentCommits(context.worktree)}`
    }

    const r = spawnSync("git", ["commit", "-m", msg], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ git commit failed (exit ${r.status}): ${r.stderr || r.stdout}`
    }

    return `Committed: ${msg}`
  },
})