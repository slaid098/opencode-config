import { spawnSync } from "child_process"
import path from "path"
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Spec status oracle. Returns current phase + NEXT action for the spec command. Call BEFORE any spec action. Read-only. Returns DONE on phase complete, NOT_DONE on missing section, AMBIGUOUS on parse error.",
  args: {
    validate: tool.schema.boolean().optional().describe("If true, show all phases detail"),
  },
  async execute(args, context) {
    const script = path.join(import.meta.dir, "..", "scripts", "spec-status.py")
    const cmdArgs = args.validate ? ["--validate"] : []
    const r = spawnSync("python3", [script, ...cmdArgs], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ spec_status failed (exit ${r.status}): ${r.stderr}`
    }
    return r.stdout.trim()
  },
})