import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  jsonToolResult,
  readJsonFile,
  resolveRunDir,
  safeResolvePath,
  spawnPython,
} from "../pipeline-core"

export function registerRefreshTool(server: McpServer, worktree: string) {
  server.registerTool(
    "refreshFields",
    {
      title: "Refresh DOCX Fields (TOC, List of Figures)",
      description:
        "Refresh all field codes (TOC, List of Figures, etc.) in the built DOCX using LibreOffice headless. Falls back to mark-dirty if LibreOffice unavailable.",
      inputSchema: z.object({
        run_dir: z.string(),
        target_file: z.string().optional(),
        strategy: z.enum(["auto", "libreoffice", "mark_dirty"]).default("auto"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, target_file, strategy }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
      const resolvedTarget = safeResolvePath([target_file, runJson?.target_file])

      if (!resolvedTarget) {
        return jsonToolResult({
          ok: false,
          error: "target_file not resolved.",
          run_dir: absRunDir,
        })
      }

      const result = await spawnPython("docx_refresh_fields.py", [
        "--target-file", resolvedTarget,
        "--strategy", strategy,
        "--run-dir", absRunDir,
      ])

      return jsonToolResult({
        ok: result.exit_code === 0,
        strategy_used: result.stdout_json?.strategy_used || result.stdout_json?.method,
        fields_refreshed: result.stdout_json?.fields_refreshed,
        note: result.stdout_json?.note,
        run_dir: absRunDir,
      })
    },
  )
}
