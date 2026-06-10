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

export function registerQATool(server: McpServer, worktree: string) {
  server.registerTool(
    "runQA",
    {
      title: "Run QA Check on Built DOCX",
      description:
        "Run quality checks on the built DOCX. Checks TOC consistency, heading structure, placeholder removal, image captions.",
      inputSchema: z.object({
        run_dir: z.string(),
        target_file: z.string().optional(),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, target_file }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
      const resolvedTarget = safeResolvePath([
        target_file,
        runJson?.target_file,
        runJson?.artifacts?.target_file,
      ])

      if (!resolvedTarget) {
        return jsonToolResult({
          ok: false,
          error: "target_file not found. Run applyOps first.",
          status: "blocked",
          run_dir: absRunDir,
        })
      }

      await mergeJsonFile(`${absRunDir}/run.json`, { target_file: resolvedTarget })

      await spawnPython("qa_docx.py", ["--run-dir", absRunDir])

      const qaReport = await readJsonFile(`${absRunDir}/qa_report.json`).catch(() => null)
      return jsonToolResult({
        ok: !!qaReport,
        qa_report: qaReport,
        run_dir: absRunDir,
      })
    },
  )
}
