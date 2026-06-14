import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { resolveRunDir, jsonToolResult } from "../pipeline-core"
import { loadOrReduce } from "../state/reducer"

export function registerInspectRunTool(server: McpServer, worktree: string) {
  server.registerTool(
    "inspectRun",
    {
      title: "Inspect Pipeline Run State",
      description:
        "Read the current state of a pipeline run. Returns phase, status, artifacts, checks, and errors. "
        + "Use this to understand what happened or where a run stopped.",
      inputSchema: z.object({
        run_dir: z.string().describe("Path to the run directory"),
      }),
      annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const state = await loadOrReduce(absRunDir)

      if (!state) {
        return jsonToolResult({
          ok: false,
          error: "No state found in run_dir",
          run_dir: absRunDir,
        })
      }

      return jsonToolResult({
        ok: true,
        run_id: state.run_id,
        run_dir: absRunDir,
        phase: state.phase,
        status: state.status,
        artifacts: Object.fromEntries(
          Object.entries(state.artifacts).map(([k, v]) => [k, { path: v.path, valid: v.valid, sha256: v.sha256 }]),
        ),
        agents: Object.fromEntries(
          Object.entries(state.agents).map(([k, v]) => [k, { status: v.status, error: v.error }]),
        ),
        checks: Object.fromEntries(
          Object.entries(state.checks).map(([k, v]) => [k, { passed: v?.passed }]),
        ),
        errors: state.errors.map((e) => ({ phase: e.phase, message: e.message, code: e.code })),
        revision: state.revision,
        created_at: state.created_at,
        updated_at: state.updated_at,
      })
    },
  )
}
