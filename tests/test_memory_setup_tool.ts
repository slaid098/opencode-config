/**
 * Tests for .opencode/tools/memory-setup.ts — the memory-setup custom tool.
 *
 * Mirror of tests/test_pipeline_status_tool.ts / test_spec_status_tool.ts:
 * the tool is a thin spawnSync wrapper around
 * ``.opencode/scripts/setup-memory.sh`` with no args.
 *
 * Runtime note: opencode ships a standalone binary with Bun bundled inside;
 * there is no separate ``bun`` CLI on the host (CI runner uses node + pytest).
 * The CI runs the equivalent Python tests in
 * ``tests/test_memory_setup_tool.py`` via the JS loader ``tests/_ts_loader.mjs``.
 * This file documents the intended TS-side test cases and is runnable under
 * ``bun test`` once a bun runtime is available on the host.
 *
 * Test cases (mirror tests/test_memory_setup_tool.py):
 *   - test_success — script exit 0 → returns trimmed stdout
 *   - test_failure — script exit 1 → returns ``⚠️ memory-setup failed (exit 1): <stderr>``
 */

import { describe, test, expect, mock } from "bun:test" with { type: "'bun-test'" }
import { spawnSync } from "child_process"
import path from "path"

const TOOL_SRC = path.resolve(import.meta.dir, "..", ".opencode", "tools", "memory-setup.ts")

describe("memory-setup tool", () => {
  test("test_success — script exit 0 returns trimmed stdout", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "  memory: ready  \n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({}, {
      sessionID: "t", messageID: "t", agent: "t",
      directory: ".", worktree: ".",
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    })
    expect(result).toBe("memory: ready")
  })

  test("test_failure — script exit 1 returns error message", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 1, stdout: "", stderr: "ERROR: OPENCODE_MEMORY_REMOTE not set" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({}, {
      sessionID: "t", messageID: "t", agent: "t",
      directory: ".", worktree: ".",
      abort: new AbortController().signal,
      metadata() {}, async ask() {},
    })
    expect(result).toContain("⚠️ memory-setup failed")
    expect(result).toContain("exit 1")
    expect(result).toContain("OPENCODE_MEMORY_REMOTE not set")
  })
})