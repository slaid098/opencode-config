/**
 * Tests for config/tools/pipeline-status.ts — the pipeline_status custom tool.
 *
 * These tests target the spawnSync-based implementation that replaced the
 * original `Bun.$` spawn (issue #99 — pipeline_status tool fails in plan-mode).
 *
 * Runtime note: opencode ships a standalone binary with Bun bundled inside;
 * there is no separate `bun` CLI on the host (CI runner uses node + pytest).
 * The CI runs the equivalent Python tests in `tests/test_pipeline_status_tool.py`
 * via the JS loader `tests/_ts_loader.mjs`. This file exists to document the
 * intended TS-side test cases and to be runnable under `bun test` once a
 * bun runtime is available on the host.
 *
 * Test cases (mirror tests/test_pipeline_status_tool.py):
 *   - test_execute_passes_correct_args
 *   - test_execute_trims_output
 *   - test_execute_non_zero_exit_returns_error
 *   - test_execute_real_pipeline_status_94 (integration)
 *   - test_execute_aborts_do_not_break_spawn_sync (regression for plan-mode)
 */

import { describe, test, expect, mock } from "bun:test" with { type: "'bun-test'" }
import { spawnSync } from "child_process"
import path from "path"

// Load the tool under test. Because the tool uses `import.meta.dir`, we
// re-resolve the script path explicitly here for testing.
const TOOL_SRC = path.resolve(import.meta.dir, "..", "config", "tools", "pipeline-status.ts")
// Re-import as a fresh module so the tool's default export is loaded.
const { default: pipelineStatusTool } = await import(TOOL_SRC)

describe("pipeline_status tool", () => {
  test("execute passes correct args to spawnSync", async () => {
    const mockSpawn = mock((_cmd: string, _args: string[]) => ({
      status: 0,
      stdout: "",
      stderr: "",
    }))
    // Re-import the tool with spawnSync stubbed out — bun:test supports
    // `mock.module` for this. See https://bun.sh/docs/test/mocking
    mock.module("child_process", () => ({ spawnSync: mockSpawn }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const t = mod.default
    await t.execute({ pr_number: 94 }, {
      sessionID: "test", messageID: "test", agent: "test",
      directory: ".", worktree: ".",
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    })
    expect(mockSpawn).toHaveBeenCalledTimes(1)
    const [cmd, args] = mockSpawn.mock.calls[0]
    expect(cmd).toBe("python3")
    expect(args[1]).toBe("94") // String(args.pr_number) — stringified
  })

  test("execute trims output", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "  trimmed  \n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ pr_number: 1 }, {
      sessionID: "t", messageID: "t", agent: "t",
      directory: ".", worktree: ".",
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    })
    expect(result).toBe("trimmed")
  })

  test("execute non-zero exit returns error message", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 1, stdout: "", stderr: "boom" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ pr_number: 1 }, {
      sessionID: "t", messageID: "t", agent: "t",
      directory: ".", worktree: ".",
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    })
    expect(result).toContain("pipeline_status failed")
    expect(result).toContain("exit 1")
    expect(result).toContain("boom")
  })

  test("execute real pipeline-status.py 94 (integration)", async () => {
    const result = await pipelineStatusTool.execute({ pr_number: 94 }, {
      sessionID: "t", messageID: "t", agent: "t",
      directory: ".", worktree: ".",
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    })
    expect(result).toContain("PR #94")
    expect(result).toMatch(/[✅❌]/)
  })

  test("execute ignores ToolContext.abort (plan-mode regression)", async () => {
    // Reproduce plan-mode: ToolContext.abort is aborted.
    const ctrl = new AbortController()
    ctrl.abort()
    const result = await pipelineStatusTool.execute({ pr_number: 94 }, {
      sessionID: "t", messageID: "t", agent: "t",
      directory: ".", worktree: ".",
      abort: ctrl.signal,
      metadata() {}, async ask() {},
    })
    // spawnSync ignores the AbortSignal, so the tool completes normally.
    expect(result).toContain("PR #94")
  })
})