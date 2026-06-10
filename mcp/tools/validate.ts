import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  jsonToolResult,
  readJsonFile,
  resolveRunDir,
  spawnPython,
} from "../pipeline-core"

export function registerValidateTool(server: McpServer, worktree: string) {
  server.registerTool(
    "validateOps",
    {
      title: "Validate Execution Ops",
      description:
        "Validate execution_ops.json for format, anchor format, required remove ops completeness, and heading level consistency.",
      inputSchema: z.object({
        run_dir: z.string(),
        ops_file: z.string().optional().describe("Path to ops JSON. Defaults to run_dir/execution_ops.json"),
        strict: z.boolean().default(false).describe("If true, return error on HIGH severity warnings"),
      }),
      annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, ops_file, strict }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const opsPath = ops_file || `${absRunDir}/execution_ops.json`

      await spawnPython("docx_validate_ops.py", [
        "--run-dir", absRunDir,
        "--ops-file", opsPath,
      ])

      const report = await readJsonFile(`${absRunDir}/execution_ops_validation.json`)
      const hasHighSeverity = report?.warnings?.some((w: any) => w.severity === "high")

      return jsonToolResult({
        ok: strict ? !hasHighSeverity : true,
        valid: !hasHighSeverity,
        warnings: report?.warnings || [],
        error_count: report?.errors?.length || 0,
        warning_count: report?.warnings?.length || 0,
        run_dir: absRunDir,
      })
    },
  )
}
