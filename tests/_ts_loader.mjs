// Test harness for .opencode/tools/pipeline-status.ts.
//
// Why this file: there is no bun/tsx/esbuild on the CI runner (only node +
// pytest). The pipeline-status.ts tool is a TypeScript module (Bun runtime
// for opencode, not runnable with plain `node`). To exercise the tool's
// execute() function in pytest, we strip TS-only syntax (import type
// annotations + ESM import -> CJS require) and load the resulting JS as a
// CommonJS module. The tool() factory from @opencode-ai/plugin is identity
// (returns its argument), so we can replace it with a passthrough shim
// without changing the tool semantics.
//
// This file is consumed by tests/test_pipeline_status_tool.py via:
//   node tests/_ts_loader.mjs <mode> [args...]
// where <mode> is one of: load, exec, exec_real.
//
// - load: print the {description, args keys} of the tool — sanity check.
// - exec: call execute({pr_number: <int>}) with a stubbed spawnSync that
//   returns whatever argv it received, plus a fixture stdout. Used by unit
//   tests to verify args passed and output trimming.
// - exec_real: call execute({pr_number: <int>}) with the REAL spawnSync,
//   used by the integration test against the real pipeline-status.py.

import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"
import { spawnSync } from "node:child_process"

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..")
const DEFAULT_TS_FILE = path.join(REPO_ROOT, ".opencode", "tools", "pipeline-status.ts")
// Parameterize via env var TS_FILE (relative to REPO_ROOT) so other TS tool
// wrappers (e.g. spec-status.ts) can be loaded by the same harness without
// breaking existing callers that don't set TS_FILE (default: pipeline-status.ts).
const TS_FILE = process.env.TS_FILE
  ? path.resolve(REPO_ROOT, process.env.TS_FILE)
  : DEFAULT_TS_FILE

// Minimal zod shim covering the methods the tool actually uses:
//   tool.schema.number().describe("...")
// At runtime (in opencode/Bun) `tool.schema` is the real zod. Here we
// only need a chainable builder that returns an object with .describe()
// — no validation occurs in execute().
function makeZodShim() {
  const chain = () => {
    const obj = {
      describe() { return obj },
      optional() { return obj },
      // Add more methods as future tool definitions need them.
    }
    return obj
  }
  return {
    number: chain,
    string: chain,
    boolean: chain,
    array: chain,
    object: chain,
  }
}
const zodShim = makeZodShim()

function stripTs(src) {
  // Minimal TS -> JS for this specific file:
  //   1) `import { spawnSync } from "child_process"` -> `const { spawnSync } = require("child_process")`
  //   2) `import { tool } from "@opencode-ai/plugin"` -> `const tool = (x) => x`
  //   3) `import path from "path"` -> `const path = require("path")`
//   4) `import.meta.dir` -> a stub pointing at .opencode/tools (so the script
//      path resolves to .opencode/scripts/pipeline-status.py)
  //   5) `args: z.ZodObject` -> the args are referenced inside execute as
  //      `args.pr_number`; the schema itself is unused at runtime here.
  //   6) Strip `: type` annotations and `async execute(args)` stays.
  let out = src
  out = out.replace(/^import\s+\{\s*spawnSync\s*\}\s+from\s+["']child_process["'];?\s*$/m, 'const { spawnSync } = require("child_process");')
  out = out.replace(/^import\s+path\s+from\s+["']path["'];?\s*$/m, 'const path = require("path");')
  out = out.replace(/^import\s+\{\s*tool\s*\}\s+from\s+["']@opencode-ai\/plugin["'];?\s*$/m, 'const tool = (x) => x;')
  // Replace `import.meta.dir` with the directory of the TS file.
  out = out.replace(/import\.meta\.dir/g, JSON.stringify(path.dirname(TS_FILE)))
  return out
}

function loadTool(spawnSyncImpl) {
  // Provide a CommonJS module sandbox so the tool file's `export default`
  // becomes accessible via `module.exports.default`.
  let src = stripTs(readFileSync(TS_FILE, "utf-8"))
  // Strip the require/const declarations we replace with sandbox args, so
  // we don't get "Identifier already declared" between Function args and
  // the in-source `const { spawnSync } = require(...)` lines.
  src = src.replace(/^const\s+\{\s*spawnSync\s*\}\s*=\s*require\(["']child_process["']\);?\s*$/m, "")
  src = src.replace(/^const\s+path\s*=\s*require\(["']path["']\);?\s*$/m, "")
  src = src.replace(/^const\s+tool\s*=\s*\(x\)\s*=>\s*x;?\s*$/m, "")
  // Convert `export default tool({...})` into `module.exports.default = tool({...})`
  const cjs = src.replace(/^export default /m, "module.exports.default = ")
  // tool shim with .schema = zodShim (since pipeline-status.ts uses tool.schema.number())
  const toolShim = (x) => x
  toolShim.schema = zodShim
  const fn = new Function(
    "module",
    "require",
    "spawnSync",
    "path",
    "tool",
    cjs + "\nreturn module.exports.default;",
  )
  return fn({ exports: {} }, (name) => {
    if (name === "child_process") return { spawnSync: spawnSyncImpl }
    if (name === "path") return path
    throw new Error("unexpected require: " + name)
  }, spawnSyncImpl, path, toolShim)
}

function buildExecArgs(tool, rawValue) {
  // Interpret ``rawValue`` (argv string) as the tool's first declared arg.
  // - pipeline-status.ts: ``pr_number`` (int) → parseInt
  // - spec-status.ts: ``validate`` (bool) → /true/i match
  // Detection is dynamic so the harness works for any single-arg tool
  // without hardcoding tool names. If the tool declares no args, return {}.
  const keys = Object.keys(tool.args || {})
  if (keys.length === 0) return {}
  const first = keys[0]
  if (first === "pr_number") return { pr_number: parseInt(rawValue, 10) }
  if (first === "validate") return { validate: /^true$/i.test(rawValue || "") }
  // Fallback heuristic: numeric → int, else bool-ish.
  return { [first]: rawValue }
}

// Multi-arg tools (commit.ts, create-pr.ts, create-issue.ts) declare several
// args (message, title, body, issue_number, labels). The single-arg
// ``buildExecArgs`` can't handle them. ``exec_stub_json`` mode passes the
// full args object as a JSON string + a JSON array of sequential stub
// responses (one per spawnSync call — commit.ts makes 2: git diff, git commit).
function buildExecArgsFromJson(rawValue) {
  return JSON.parse(rawValue)
}

function buildStubSequencer(responses) {
  // Return a stub function that returns responses[callIndex] for each call,
  // cycling through the list if there are more calls than responses.
  let idx = 0
  return (cmd, args, opts) => {
    const r = responses[idx % responses.length]
    idx++
    return { status: r.status, stdout: r.stdout ?? "", stderr: r.stderr ?? "" }
  }
}

function main() {
  const mode = process.argv[2]
  if (!mode) {
    console.error("usage: node _ts_loader.mjs <mode> [args...]")
    process.exit(2)
  }
  if (mode === "load") {
    const t = loadTool(spawnSync)
    console.log(JSON.stringify({ description: t.description, args: Object.keys(t.args) }))
    return
  }
  if (mode === "exec_stub") {
    // Args: <first_arg_value> <stub_status> <stub_stdout> <stub_stderr>
    // The first arg is interpreted based on which tool is loaded:
    // - pipeline-status.ts declares ``pr_number`` (int)
    // - spec-status.ts declares ``validate`` (bool)
    // Detected dynamically from ``t.args`` keys so the harness stays generic.
    const stubStatus = parseInt(process.argv[4], 10)
    const stubStdout = process.argv[5]
    const stubStderr = process.argv[6] || ""
    const callLog = []
    const stub = (cmd, args, opts) => {
      callLog.push({ cmd, args, opts })
      return { status: stubStatus, stdout: stubStdout, stderr: stubStderr }
    }
    const t = loadTool(stub)
    const execArgs = buildExecArgs(t, process.argv[3])
    t.execute(execArgs, {
      // ToolContext — only fields the tool actually touches. Our tool
      // touches none of the ctx fields, so this can be empty-ish.
      sessionID: "test", messageID: "test", agent: "test",
      directory: REPO_ROOT, worktree: REPO_ROOT,
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    }).then(
      (result) => {
        console.log(JSON.stringify({ result, calls: callLog }))
      },
      (err) => {
        console.log(JSON.stringify({ error: String(err), calls: callLog }))
      },
    )
    return
  }
  if (mode === "exec_stub_json") {
    // Multi-arg tools (commit.ts, create-pr.ts, create-issue.ts).
    // Args: <args_json> <responses_json>
    //   args_json — JSON string of the args object, e.g. {"message":"feat(x): y"}
    //   responses_json — JSON array of {status, stdout, stderr} stub
    //     responses, returned sequentially per spawnSync call. Tools that
    //     make N spawnSync calls need N entries (extra calls cycle back).
    const execArgs = buildExecArgsFromJson(process.argv[3])
    const responses = JSON.parse(process.argv[4])
    const callLog = []
    const stub = (cmd, args, opts) => {
      callLog.push({ cmd, args, opts })
      const r = responses[callLog.length - 1] || responses[responses.length - 1]
      return { status: r.status, stdout: r.stdout ?? "", stderr: r.stderr ?? "" }
    }
    const t = loadTool(stub)
    t.execute(execArgs, {
      sessionID: "test", messageID: "test", agent: "test",
      directory: REPO_ROOT, worktree: REPO_ROOT,
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    }).then(
      (result) => {
        console.log(JSON.stringify({ result, calls: callLog }))
      },
      (err) => {
        console.log(JSON.stringify({ error: String(err), calls: callLog }))
      },
    )
    return
  }
  if (mode === "exec_real") {
    const t = loadTool(spawnSync) // use real spawnSync
    const execArgs = buildExecArgs(t, process.argv[3])
    t.execute(execArgs, {
      sessionID: "test", messageID: "test", agent: "test",
      directory: REPO_ROOT, worktree: REPO_ROOT,
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    }).then(
      (result) => console.log(JSON.stringify({ result })),
      (err) => console.log(JSON.stringify({ error: String(err) })),
    )
    return
  }
  console.error("unknown mode: " + mode)
  process.exit(2)
}

main()