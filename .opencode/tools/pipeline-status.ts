import { spawnSync } from "child_process"
import path from "path"
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Pipeline status oracle. Returns current phase + NEXT action for a PR. Call BEFORE any pipeline action. Read-only. Blocks up to 5 min while CI runs (polling Actions API). Returns DONE on green, NOT_DONE on failure, AMBIGUOUS on timeout/API error.",
  args: {
    pr_number: tool.schema.number().describe("PR number to check"),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "..", "scripts", "pipeline-status.py")
    const r = spawnSync("python3", [script, String(args.pr_number)], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ pipeline_status failed (exit ${r.status}): ${r.stderr}`
    }
    return r.stdout.trim()
  },
})