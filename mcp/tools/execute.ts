import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  jsonToolResult,
  mergeJsonFile,
  readJsonFile,
  resolveRunDir,
  safeResolvePath,
  spawnPython,
} from "../pipeline-core"

export function registerExecuteTool(server: McpServer, worktree: string) {
  server.registerTool(
    "applyOps",
    {
      title: "Apply Execution Ops to DOCX",
      description:
        "Execute execution_ops.json ops on the target DOCX file. Reads target_file from run.json or explicit param.",
      inputSchema: z.object({
        run_dir: z.string(),
        target_file: z.string().optional().describe("Override target file path. Falls back to run.json.target_file"),
        fail_fast: z.boolean().default(false),
      }),
      annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ run_dir, target_file, fail_fast }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
      const resolvedTarget = safeResolvePath([target_file, runJson?.target_file])

      if (!resolvedTarget) {
        return jsonToolResult({
          ok: false,
          error: "target_file not set in run.json and not passed. Run inspectTemplate first.",
          run_dir: absRunDir,
        })
      }

      await mergeJsonFile(`${absRunDir}/run.json`, {
        target_file: resolvedTarget,
        template_file: runJson?.template_file || "",
        status: "executing",
      })

      const args = ["--run-dir", absRunDir]
      if (runJson?.template_file) {
        args.push("--template-file", runJson.template_file)
      }
      args.push("--target-file", resolvedTarget)
      if (fail_fast) args.push("--fail-fast")

      const result = await spawnPython("execute_execution_ops.py", args)

      await mergeJsonFile(`${absRunDir}/run.json`, {
        status: result.exit_code === 0 ? "built" : "failed",
        target_file: resolvedTarget,
      })

      const report = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => null)
      return jsonToolResult({
        ok: result.exit_code === 0,
        target_file: resolvedTarget,
        ops_applied: report?.succeeded || 0,
        ops_failed: report?.failed || 0,
        run_dir: absRunDir,
      })
    },
  )
}
