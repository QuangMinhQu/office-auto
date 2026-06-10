import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  createRunDir,
  jsonToolResult,
  mergeJsonFile,
  readJsonFile,
  resolveRunDir,
  resolveWorkspacePath,
  spawnPython,
} from "../pipeline-core"

function buildCompactInspection(inspection: any, contentMap: any, stylesForLlm: any) {
  const rawAnchor = contentMap?.recommended_insert_anchor
    || stylesForLlm?.recommended_anchor
    || inspection?.content_map?.recommended_insert_anchor
    || null

  const allParaIds = inspection?.all_para_ids || []
  const bodyPlaceholders = contentMap?.body_placeholders || inspection?.content_map?.body_placeholders || {}
  const bodyParaIds: string[] = Array.isArray(bodyPlaceholders.para_ids) ? bodyPlaceholders.para_ids : []

  return {
    CRITICAL_FIRST_OP_ANCHOR: rawAnchor ? `/body/p[@paraId=${rawAnchor}]` : null,
    anchor_format_note: "MUST use /body/p[@paraId=XXXX] format.",
    toc_last_para_id: inspection?.toc_entries_raw?.at(-1)?.para_id
      ? `/body/p[@paraId=${inspection.toc_entries_raw.at(-1).para_id}]`
      : null,
    front_matter_last_para_id: inspection?.front_matter_boundary?.last_para_id || null,
    body_text_style: stylesForLlm?.body_text_style || inspection?.styles_for_llm?.body_text_style || null,
    heading_map: stylesForLlm?.heading_map || inspection?.styles_for_llm?.heading_map || {},
    available_styles: (stylesForLlm?.available_styles || inspection?.styles_for_llm?.available_styles || [])
      .slice(0, 15)
      .map((s: any) => ({ name: s.name, style_id: s.style_id, use_for: s.use_for })),
    do_not_use_styles: stylesForLlm?.do_not_use_styles || inspection?.styles_for_llm?.do_not_use_styles || [],
    anchor_candidates: allParaIds
      .filter((p: any) => p.is_front_matter)
      .slice(-8)
      .map((p: any) => ({
        anchor: `/body/p[@paraId=${p.para_id}]`,
        text_preview: (p.text_preview || "").slice(0, 40),
        is_toc_style: (p.style_name || "").toLowerCase().includes("toc"),
      })),
    body_placeholders: {
      para_ids: bodyParaIds.slice(0, 50),
      description: bodyPlaceholders.description || "",
      total_count: bodyParaIds.length,
    },
    placeholder_note: "Only first 50 body placeholders shown. Full list in docx_inspect_content_map.json",
  }
}

export function registerInspectTool(server: McpServer, worktree: string) {
  server.registerTool(
    "inspectTemplate",
    {
      title: "Inspect DOCX Template",
      description:
        "Run full inspection on a DOCX template. Creates run_dir, runs docx_inspect.py, returns compact inspection payload for planning.",
      inputSchema: z.object({
        template_file: z.string().describe("Absolute or workspace-relative path to .docx template"),
        run_dir: z.string().optional().describe("Optional: reuse existing run_dir. Auto-generated if omitted."),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ template_file, run_dir }) => {
      const absTpl = resolveWorkspacePath(worktree, template_file)
      const absRunDir = run_dir
        ? resolveRunDir(worktree, run_dir)
        : await createRunDir(worktree, absTpl)

      const targetFile = absTpl.replace(/_template/, "").replace(/\.docx$/, "_output.docx")
      await mergeJsonFile(`${absRunDir}/run.json`, {
        template_file: absTpl,
        target_file: targetFile,
        status: "inspecting",
      })

      const result = await spawnPython("docx_inspect.py", [
        "--template-file", absTpl,
        "--run-dir", absRunDir,
      ])

      if (result.exit_code !== 0) {
        return jsonToolResult({
          ok: false,
          error: "Inspection failed",
          stderr: result.stderr,
          run_dir: absRunDir,
        })
      }

      const inspection = await readJsonFile(`${absRunDir}/docx_inspect_output.json`)
      const contentMap = await readJsonFile(`${absRunDir}/docx_inspect_content_map.json`)
      const stylesForLlm = await readJsonFile(`${absRunDir}/docx_inspect_styles_for_llm.json`)

      await mergeJsonFile(`${absRunDir}/run.json`, { status: "inspected" })

      return jsonToolResult({
        ok: true,
        run_dir: absRunDir,
        target_file: targetFile,
        inspection_file: `${absRunDir}/docx_inspect_output.json`,
        compact: buildCompactInspection(inspection, contentMap, stylesForLlm),
      })
    },
  )
}
