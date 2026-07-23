import { spawnSync } from "child_process"
import path from "path"
import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Toggle cloudflare tunnel. First call starts, second call stops. No arguments needed.",
  args: {},
  async execute(_args, context) {
    const script = path.join(import.meta.dir, "..", "scripts", "tunnel.sh")
    const r = spawnSync("bash", [script], {
      encoding: "utf-8",
      cwd: context.worktree,
    })
    if (r.status !== 0) {
      return `⚠️ tunnel failed (exit ${r.status}): ${r.stderr}`
    }
    return r.stdout.trim()
  },
})
