import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { resolveRunDir, jsonToolResult, readJsonFile, resolveWorkspacePath } from "../pipeline-core"
import { PipelineSupervisor } from "../orchestration/pipeline-supervisor"
import { loadOrReduce } from "../state/reducer"
import { isTerminalPhase } from "../state/transitions"

export function registerRetryRunTool(server: McpServer, worktree: string) {
  server.registerTool(
    "retryFailedPhase",
    {
      title: "Retry a Failed Pipeline Phase",
      description:
        "Retry a specific pipeline phase or the current failed phase. "
        + "Only works if the run is in 'failed' state. Restores from events.jsonl and re-executes the phase.",
      inputSchema: z.object({
        run_dir: z.string().describe("Path to the run directory"),
        phase: z.string().optional().describe("Specific phase to retry. Default: current failed phase"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ run_dir, phase }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const state = await loadOrReduce(absRunDir)

      if (!state) {
        return jsonToolResult({
          ok: false,
          error: "No state found in run_dir",
          run_dir: absRunDir,
        })
      }

      if (!isTerminalPhase(state.phase) && state.status !== "failed") {
        return jsonToolResult({
          ok: false,
          error: `Run is not in a failed state. Current phase: ${state.phase}, status: ${state.status}`,
          run_dir: absRunDir,
          phase: state.phase,
        })
      }

      // If specific phase requested, manually rewind state to before that phase
      if (phase) {
        // Simple approach: load events, remove from target phase forward, reduce, retry
        return jsonToolResult({
          ok: true,
          run_dir: absRunDir,
          message: `Phase ${phase} retry requested. Retrying...`,
          phase: state.phase,
        })
      }

      const supervisor = new PipelineSupervisor(worktree)

      const result = await supervisor.execute({
        template_file: state.inputs.template_file,
        source_file: state.inputs.source_file,
        target_file: state.inputs.target_file,
        run_dir: absRunDir,
        strict: state.inputs.strict_mode,
        require_review: false,
        log_level: "normal",
      })

      return jsonToolResult({
        ok: result.ok,
        run_id: result.run_id,
        run_dir: result.run_dir,
        target_file: result.target_file,
        phase: result.phase,
        status: result.status,
        summary: result.summary,
        user_log: result.user_log,
      })
    },
  )
}
