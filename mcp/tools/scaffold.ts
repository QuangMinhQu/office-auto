import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  jsonToolResult,
  parseMarkdownHeadings,
  readJsonFile,
  readTextFile,
  resolveRunDir,
  resolveWorkspacePath,
  writeJsonFile,
} from "../pipeline-core"

export function registerScaffoldTool(server: McpServer, worktree: string) {
  server.registerTool(
    "prepareInsertPlan",
    {
      title: "DOCX Insert Plan Scaffold",
      description:
        "Aggregate inspection output and source markdown headings into a compact reasoning scaffold for execution planning.",
      inputSchema: z.object({
        run_dir: z.string(),
        content_file: z.string().default(""),
      }),
      annotations: { readOnlyHint: true, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, content_file }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const contentFile = content_file ? resolveWorkspacePath(worktree, content_file) : ""
      const inspection = await readJsonFile(`${absRunDir}/docx_inspect_output.json`)
      const stylesForLlm = await readJsonFile(`${absRunDir}/docx_inspect_styles_for_llm.json`)
      const contentMap = await readJsonFile(`${absRunDir}/docx_inspect_content_map.json`)
      let headings: Array<{ level: number; text: string }> = []
      if (contentFile) {
        try {
          const markdownText = await readTextFile(contentFile)
          headings = parseMarkdownHeadings(markdownText)
        } catch {
          headings = []
        }
      }

      const rawAnchor = contentMap?.recommended_insert_anchor
        || stylesForLlm?.recommended_anchor
        || inspection?.content_map?.recommended_insert_anchor
        || null
      const bodyPlaceholders = contentMap?.body_placeholders || inspection?.content_map?.body_placeholders || {}
      const bodyParaIds: string[] = Array.isArray(bodyPlaceholders.para_ids) ? bodyPlaceholders.para_ids : []
      const frontMatterBlock = contentMap?.front_matter || inspection?.content_map?.front_matter || {}

      const scaffold = {
        run_dir: absRunDir,
        source_file: contentFile || null,
        recommended_anchor: rawAnchor
          ? `/body/p[@paraId=${rawAnchor}]`
          : null,
        CRITICAL_FIRST_OP_ANCHOR: rawAnchor
          ? `/body/p[@paraId=${rawAnchor}]`
          : null,
        anchor_format_note: "CRITICAL: anchor MUST be /body/p[@paraId=XXXX] format. Never use raw hex.",
        toc_last_para_id: inspection?.front_matter_boundary?.last_para_id || null,
        front_matter_last_para_id: inspection?.front_matter_boundary?.last_para_id || null,
        body_text_style: stylesForLlm?.body_text_style || inspection?.styles_for_llm?.body_text_style || null,
        heading_map: stylesForLlm?.heading_map || inspection?.styles_for_llm?.heading_map || {},
        available_styles: (stylesForLlm?.available_styles || inspection?.styles_for_llm?.available_styles || [])
          .slice(0, 15)
          .map((s: any) => ({ name: s.name, style_id: s.style_id, use_for: s.use_for })),
        do_not_use_styles: stylesForLlm?.do_not_use_styles || inspection?.styles_for_llm?.do_not_use_styles || [],
        front_matter: frontMatterBlock,
        body_placeholders: {
          para_ids: bodyParaIds.slice(0, 50),
          description: bodyPlaceholders.description || "",
          total_count: bodyParaIds.length,
          details: (inspection?.all_para_ids || [])
            .filter((p: any) => !p.is_front_matter && bodyParaIds.includes(p.para_id))
            .slice(0, 50)
            .map((p: any) => ({
              paraId: p.para_id,
              text_preview: (p.text_preview || "").slice(0, 60),
              is_front_matter: p.is_front_matter || false,
              style_name: p.style_name || null,
            })),
        },
        placeholder_note: "Only first 50 body placeholders shown. Full list in docx_inspect_content_map.json. Each entry carries is_front_matter and style_name for LLM reasoning.",
        markdown_headings: headings,
        markdown_heading_count: headings.length,
        paragraph_count: Array.isArray(inspection?.paragraph_sample) ? inspection.paragraph_sample.length : 0,
      }

      const scaffoldFile = `${absRunDir}/insert_plan_scaffold.json`
      await writeJsonFile(scaffoldFile, scaffold)
      return jsonToolResult({
        ok: true,
        scaffold_file: scaffoldFile,
        scaffold,
      })
    },
  )
}
