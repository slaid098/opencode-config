/**
 * Tests for .opencode/tools/create-issue.ts — the create-issue custom tool.
 *
 * Mirror of tests/test_pipeline_status_tool.ts / test_memory_setup_tool.ts:
 * the tool is a spawnSync wrapper around `gh issue create` with title/body
 * validation.
 *
 * Runtime note: opencode ships a standalone binary with Bun bundled inside;
 * there is no separate `bun` CLI on the host (CI runner uses node + pytest).
 * The CI runs the equivalent Python tests in tests/test_create_issue_tool.py
 * via the JS loader tests/_ts_loader.mjs (exec_stub_json mode for multi-arg
 * tools). This file documents the intended TS-side test cases and is
 * runnable under `bun test` once a bun runtime is available on the host.
 *
 * Test cases (mirror tests/test_create_issue_tool.py):
 *   - test_valid_issue — valid title + body → "Issue created: <url>"
 *   - test_title_too_long — title >80 chars → error
 *   - test_missing_kontekst — body missing ## Контекст → error
 *   - test_missing_zadacha — body missing ## Задача → error
 *   - test_missing_kriterii — body missing ## Критерии приемки → error
 *   - test_latin_only_body — body without Cyrillic → error
 */

import { describe, test, expect, mock } from "bun:test" with { type: "'bun-test'" }
import { spawnSync } from "child_process"
import path from "path"

const TOOL_SRC = path.resolve(import.meta.dir, "..", ".opencode", "tools", "create-issue.ts")

function ctx() {
  return {
    sessionID: "t", messageID: "t", agent: "t",
    directory: ".", worktree: ".",
    abort: new AbortController().signal,
    metadata() {}, async ask() {},
  }
}

const VALID_BODY = "## Контекст\nНужен tool\n\n## Задача\nСоздать tool\n\n## Критерии приемки\nTool работает"

describe("create-issue tool", () => {
  test("test_valid_issue — valid title + body succeeds", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "https://github.com/x/y/issues/1\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): add create-issue tool",
      body: VALID_BODY,
    }, ctx())
    expect(result).toBe("Issue created: https://github.com/x/y/issues/1")
  })

  test("test_title_too_long — title >80 chars → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const longDesc = "x".repeat(81)
    const result = await mod.default.execute({
      title: `feat(tools): ${longDesc}`,
      body: VALID_BODY,
    }, ctx())
    expect(result).toContain("must match format")
  })

  test("test_missing_kontekst — body missing ## Контекст → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## Задача\nСделать\n\n## Критерии приемки\nГотово",
    }, ctx())
    expect(result).toContain("## Контекст")
  })

  test("test_missing_zadacha — body missing ## Задача → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## Контекст\nКонтекст\n\n## Критерии приемки\nГотово",
    }, ctx())
    expect(result).toContain("## Задача")
  })

  test("test_missing_kriterii — body missing ## Критерии приемки → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## Контекст\nКонтекст\n\n## Задача\nСделать",
    }, ctx())
    expect(result).toContain("## Критерии приемки")
  })

  test("test_latin_only_body — body without Cyrillic → error", async () => {
    // NOTE: spec validation order checks headings (## Контекст, ## Задача,
    // ## Критерии приемки) BEFORE the Cyrillic check. Since the headings
    // themselves are Cyrillic, a body that passes the heading checks always
    // passes the Cyrillic check. Therefore a Latin-only body (no Cyrillic)
    // also lacks the Russian headings and fails on the heading check first.
    // The Cyrillic check is effectively dead code given the heading checks —
    // documented as spec issue in handoff.
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## Context\nSome\n\n## Task\nDo it\n\n## Acceptance criteria\nDone",
    }, ctx())
    // Body lacks Russian headings → heading check fires (not Cyrillic check).
    expect(result).toContain("## Контекст")
  })
})