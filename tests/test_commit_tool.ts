/**
 * Tests for .opencode/tools/commit.ts — the commit custom tool.
 *
 * Mirror of tests/test_pipeline_status_tool.ts / test_memory_setup_tool.ts:
 * the tool is a spawnSync wrapper around `git commit` with format validation.
 *
 * Runtime note: opencode ships a standalone binary with Bun bundled inside;
 * there is no separate `bun` CLI on the host (CI runner uses node + pytest).
 * The CI runs the equivalent Python tests in tests/test_commit_tool.py via
 * the JS loader tests/_ts_loader.mjs (exec_stub_json mode for multi-arg
 * tools). This file documents the intended TS-side test cases and is
 * runnable under `bun test` once a bun runtime is available on the host.
 *
 * Test cases (mirror tests/test_commit_tool.py):
 *   - test_valid_commit — valid message + staged files → "Committed: <msg>"
 *   - test_no_scope — missing scope → error with rules
 *   - test_cyrillic — Cyrillic in message → error
 *   - test_multiline — message with \n → error
 *   - test_too_long — description >72 chars → error
 *   - test_no_staged — no staged files → error
 *   - test_wrong_type — type "wip" → error
 */

import { describe, test, expect, mock } from "bun:test" with { type: "'bun-test'" }
import { spawnSync } from "child_process"
import path from "path"

const TOOL_SRC = path.resolve(import.meta.dir, "..", ".opencode", "tools", "commit.ts")

function ctx() {
  return {
    sessionID: "t", messageID: "t", agent: "t",
    directory: ".", worktree: ".",
    abort: new AbortController().signal,
    metadata() {}, async ask() {},
  }
}

describe("commit tool", () => {
  test("test_valid_commit — valid message + staged files succeeds", async () => {
    // commit.ts makes 2 spawnSync calls: git diff --cached, git commit.
    // First: staged files exist (non-empty stdout). Second: commit success.
    let callIdx = 0
    mock.module("child_process", () => ({
      spawnSync: () => {
        callIdx++
        if (callIdx === 1) return { status: 0, stdout: "file.txt\n", stderr: "" }
        return { status: 0, stdout: "", stderr: "" }
      },
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ message: "feat(tools): add commit tool" }, ctx())
    expect(result).toBe("Committed: feat(tools): add commit tool")
  })

  test("test_no_scope — missing scope → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "file.txt\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ message: "feat: no scope here" }, ctx())
    expect(result).toContain("must match format")
  })

  test("test_cyrillic — Cyrillic in message → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "file.txt\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ message: "feat(тест): привет" }, ctx())
    expect(result).toContain("must be in English")
  })

  test("test_multiline — message with newline → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "file.txt\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ message: "feat(tools): line1\nline2" }, ctx())
    expect(result).toContain("must be single-line")
  })

  test("test_too_long — description >72 chars → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "file.txt\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const longDesc = "x".repeat(73)
    const result = await mod.default.execute({ message: `feat(tools): ${longDesc}` }, ctx())
    expect(result).toContain("must match format")
  })

  test("test_no_staged — no staged files → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ message: "feat(tools): valid message" }, ctx())
    expect(result).toContain("No staged files")
  })

  test("test_wrong_type — type 'wip' → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "file.txt\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({ message: "wip(tools): not a valid type" }, ctx())
    expect(result).toContain("must match format")
  })
})