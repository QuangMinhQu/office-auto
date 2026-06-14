import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { resolveRunDir, jsonToolResult, readJsonFile, resolveWorkspacePath } from "../pipeline-core"
import { PipelineSupervisor } from "../orchestration/pipeline-supervisor"

export function registerResumeRunTool(server: McpServer, worktree: string) {
  server.registerTool(
    "resumeReportRun",
    {
      title: "Resume a Paused or Interrupted Pipeline Run",
      description:
        "Resume a pipeline run from where it stopped. Replays events.jsonl, verifies artifact checksums, and continues from the next phase. "
        + "Does NOT re-run completed phases.",
      inputSchema: z.object({
        run_dir: z.string().describe("Path to the run directory to resume"),
        log_level: z.enum(["brief", "normal", "debug"]).default("brief"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, log_level }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => null)

      if (!runJson) {
        return jsonToolResult({
          ok: false,
          error: "No run.json found in run_dir. Cannot resume.",
          run_dir: absRunDir,
        })
      }

      const supervisor = new PipelineSupervisor(worktree)

      const result = await supervisor.execute({
        template_file: runJson.inputs?.template_file || runJson.template_file,
        source_file: runJson.inputs?.source_file || runJson.source_file,
        target_file: runJson.inputs?.target_file || runJson.target_file,
        run_dir: absRunDir,
        strict: runJson.inputs?.strict_mode ?? runJson.strict_mode ?? true,
        require_review: false,
        log_level,
      })

      return jsonToolResult({
        ok: result.ok,
        run_id: result.run_id,
        run_dir: result.run_dir,
        target_file: result.target_file,
        phase: result.phase,
        status: result.status,
        summary: result.summary,
        ...(log_level === "debug" ? { debug: result.debug } : {}),
        user_log: result.user_log,
      })
    },
  )
}
