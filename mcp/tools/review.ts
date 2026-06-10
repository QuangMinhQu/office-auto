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

export function registerReviewTool(server: McpServer, worktree: string) {
  server.registerTool(
    "reviewOutput",
    {
      title: "Review DOCX Output vs. Source",
      description:
        "Compare built DOCX against source markdown. Returns diff summary and review report.",
      inputSchema: z.object({
        run_dir: z.string(),
        target_file: z.string().optional(),
        source_file: z.string().optional(),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, target_file, source_file }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
      const resolvedTarget = safeResolvePath([target_file, runJson?.target_file])
      const resolvedSource = safeResolvePath([source_file, runJson?.source_file])

      if (!resolvedTarget) {
        return jsonToolResult({
          ok: false,
          error: "target_file not resolved. Check run.json.",
          status: "blocked",
          run_dir: absRunDir,
        })
      }

      await mergeJsonFile(`${absRunDir}/run.json`, { target_file: resolvedTarget })
      if (resolvedSource) {
        await mergeJsonFile(`${absRunDir}/run.json`, { source_file: resolvedSource })
      }

      await spawnPython("review_docx.py", ["--run-dir", absRunDir])

      const reviewReport = await readJsonFile(`${absRunDir}/review_report.json`).catch(() => null)
      return jsonToolResult({
        ok: !!reviewReport,
        review_report: reviewReport,
        run_dir: absRunDir,
      })
    },
  )
}
