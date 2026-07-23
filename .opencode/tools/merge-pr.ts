import { spawnSync } from "child_process"
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Merge a PR via squash + delete branch. Orchestrator-safe wrapper for `gh pr merge N --squash --delete-branch`. Main agent calls this tool instead of raw bash, aligning with the pure-orchestrator model (ADR-012 tool-led).",
  args: {
    pr_number: tool.schema.number().describe("PR number to merge"),
  },
  async execute(args, context) {
    const r = spawnSync("gh", [
      "pr", "merge", String(args.pr_number),
      "--squash", "--delete-branch",
    ], {
      encoding: "utf-8",
      cwd: context.worktree,
    })

    if (r.status !== 0) {
      return `⚠️ merge_pr failed for PR #${args.pr_number} (exit ${r.status}): ${r.stderr || r.stdout}`
    }

    return `PR #${args.pr_number} merged successfully (squash, branch deleted).`
  },
})
