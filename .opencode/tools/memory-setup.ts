import { spawnSync } from "child_process"
import path from "path"
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Initialize or sync opencode-memory. Clones remote repo, installs post-commit hook for auto-push, rebuilds RAG index. Idempotent — safe to run multiple times. No arguments needed.",
  args: {},
  async execute(_args, context) {
    const script = path.join(import.meta.dir, "..", "scripts", "setup-memory.sh")
    const r = spawnSync("bash", [script], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ memory-setup failed (exit ${r.status}): ${r.stderr || r.stdout}`
    }
    return r.stdout.trim()
  },
})