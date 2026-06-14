import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { resolveWorkspacePath, jsonToolResult } from "../pipeline-core"
import { PipelineSupervisor } from "../orchestration/pipeline-supervisor"

export function registerCreateReportTool(server: McpServer, worktree: string) {
  server.registerTool(
    "createReportFromMarkdown",
    {
      title: "Create DOCX Report from Markdown (v3 Deterministic Pipeline)",
      description:
        "Orchestrate the full deterministic pipeline: inspect → source_packet → mapping → compile → validate → apply → verify → QA → review → refresh → final_gate. "
        + "This is the PRIMARY tool for generating reports. Do not call individual phase tools directly. "
        + "LLM only decides style_map + replace_range; everything else is deterministic.",
      inputSchema: z.object({
        template_file: z.string().describe("Path to the .docx template file"),
        source_file: z.string().describe("Path to the source .md markdown file"),
        target_file: z.string().optional().describe("Output DOCX path. Default: derived from template"),
        run_dir: z.string().optional().describe("Optional: reuse existing run_dir for resume"),
        style_map: z.string().optional().describe("Path to style_map.json. If omitted, uses defaults from inspection"),
        replace_range: z.string().optional().describe("Path to replace_range.json. If omitted, uses scaffold defaults"),
        strict: z.boolean().default(true).describe("If true, hard-block on validation failure"),
        require_review: z.boolean().default(false).describe("If true, require LLM review phase"),
        log_level: z.enum(["brief", "normal", "debug"]).default("brief").describe("Log verbosity"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ template_file, source_file, target_file, run_dir, style_map, replace_range, strict, require_review, log_level }) => {
      const supervisor = new PipelineSupervisor(worktree)

      const result = await supervisor.execute({
        template_file,
        source_file,
        target_file,
        run_dir,
        style_map,
        replace_range,
        strict,
        require_review,
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
        ...(log_level !== "brief" ? { user_log: result.user_log } : { user_log: result.user_log.slice(0, 3) }),
      })
    },
  )
}
