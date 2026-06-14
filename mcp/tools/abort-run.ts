import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { resolveRunDir, jsonToolResult } from "../pipeline-core"
import { releaseRunLock } from "../state/lock"
import { loadOrReduce, writeSnapshot } from "../state/reducer"
import type { PipelineState } from "../state/pipeline-state"

export function registerAbortRunTool(server: McpServer, worktree: string) {
  server.registerTool(
    "abortRun",
    {
      title: "Abort a Pipeline Run",
      description:
        "Mark a pipeline run as failed and release its lock. "
        + "The run directory and all artifacts are preserved for inspection.",
      inputSchema: z.object({
        run_dir: z.string().describe("Path to the run directory"),
        reason: z.string().describe("Reason for aborting"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, reason }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const state = await loadOrReduce(absRunDir)

      if (!state) {
        return jsonToolResult({
          ok: false,
          error: "No state found in run_dir. Nothing to abort.",
          run_dir: absRunDir,
        })
      }

      const abortedState: PipelineState = {
        ...state,
        phase: "failed",
        status: "failed",
        errors: [
          ...state.errors,
          {
            phase: state.phase,
            message: `Aborted: ${reason}`,
            timestamp: new Date().toISOString(),
            recoverable: false,
          },
        ],
        updated_at: new Date().toISOString(),
        revision: state.revision + 1,
      }

      await writeSnapshot(absRunDir, abortedState)
      await releaseRunLock(absRunDir)

      return jsonToolResult({
        ok: true,
        run_id: state.run_id,
        run_dir: absRunDir,
        previous_phase: state.phase,
        reason,
      })
    },
  )
}
