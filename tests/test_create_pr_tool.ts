/**
 * Tests for .opencode/tools/create-pr.ts — the create-pr custom tool.
 *
 * Mirror of tests/test_pipeline_status_tool.ts / test_memory_setup_tool.ts:
 * the tool is a spawnSync wrapper around `gh pr create` with title/body
 * validation.
 *
 * Runtime note: opencode ships a standalone binary with Bun bundled inside;
 * there is no separate `bun` CLI on the host (CI runner uses node + pytest).
 * The CI runs the equivalent Python tests in tests/test_create_pr_tool.py
 * via the JS loader tests/_ts_loader.mjs (exec_stub_json mode for multi-arg
 * tools). This file documents the intended TS-side test cases and is
 * runnable under `bun test` once a bun runtime is available on the host.
 *
 * Test cases (mirror tests/test_create_pr_tool.py):
 *   - test_valid_pr — valid title + body → "PR created: <url>"
 *   - test_missing_scope — title without scope → error
 *   - test_missing_chto_sdelano — body missing ## Что сделано → error
 *   - test_missing_pochemu — body missing ## Почему → error
 *   - test_latin_only_body — body without Cyrillic → error
 *   - test_issue_linkage — issue_number → body gets Closes #N
 */

import { describe, test, expect, mock } from "bun:test" with { type: "'bun-test'" }
import { spawnSync } from "child_process"
import path from "path"

const TOOL_SRC = path.resolve(import.meta.dir, "..", ".opencode", "tools", "create-pr.ts")

function ctx() {
  return {
    sessionID: "t", messageID: "t", agent: "t",
    directory: ".", worktree: ".",
    abort: new AbortController().signal,
    metadata() {}, async ask() {},
  }
}

const VALID_BODY = "## Что сделано\nДобавлен tool\n\n## Почему\nНужна валидация"

describe("create-pr tool", () => {
  test("test_valid_pr — valid title + body succeeds", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "https://github.com/x/y/pull/1\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): add create-pr tool",
      body: VALID_BODY,
    }, ctx())
    expect(result).toBe("PR created: https://github.com/x/y/pull/1")
  })

  test("test_missing_scope — title without scope → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat: no scope",
      body: VALID_BODY,
    }, ctx())
    expect(result).toContain("must match format")
  })

  test("test_missing_chto_sdelano — body missing ## Что сделано → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## Почему\nПотому что",
    }, ctx())
    expect(result).toContain("## Что сделано")
  })

  test("test_missing_pochemu — body missing ## Почему → error", async () => {
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## Что сделано\nСделано",
    }, ctx())
    expect(result).toContain("## Почему")
  })

  test("test_latin_only_body — body without Cyrillic → error", async () => {
    // NOTE: spec validation order checks headings (## Что сделано, ## Почему)
    // BEFORE the Cyrillic check. Since the headings themselves are Cyrillic,
    // a body that passes the heading checks always passes the Cyrillic check.
    // Therefore a Latin-only body (no Cyrillic) also lacks the Russian headings
    // and fails on the heading check first. The Cyrillic check is effectively
    // dead code given the heading checks — documented as spec issue in handoff.
    mock.module("child_process", () => ({
      spawnSync: () => ({ status: 0, stdout: "url\n", stderr: "" }),
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: "## What done\nSomething\n\n## Why\nBecause",
    }, ctx())
    // Body lacks Russian headings → heading check fires (not Cyrillic check).
    expect(result).toContain("## Что сделано")
  })

  test("test_issue_linkage — issue_number appends Closes #N to body", async () => {
    let capturedArgs
    mock.module("child_process", () => ({
      spawnSync: (_cmd, args) => {
        capturedArgs = args
        return { status: 0, stdout: "https://github.com/x/y/pull/5\n", stderr: "" }
      },
    }))
    const mod = await import(TOOL_SRC + "?t=" + Date.now())
    const result = await mod.default.execute({
      title: "feat(tools): valid title",
      body: VALID_BODY,
      issue_number: 37,
    }, ctx())
    expect(result).toBe("PR created: https://github.com/x/y/pull/5")
    // body is the 4th arg (after --title, title, --body)
    const bodyArg = capturedArgs[capturedArgs.indexOf("--body") + 1]
    expect(bodyArg).toContain("Closes #37")
  })
})