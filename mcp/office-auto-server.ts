import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { z } from "zod"
import {
  fileExists,
  parseMarkdownHeadings,
  readJsonFile,
  readTextFile,
  resolveRunDir,
  resolveWorkspacePath,
  writeJsonFile,
} from "./pipeline-core"

const WORKTREE = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
const server = new McpServer({ name: "office-auto", version: "1.0.0" })

function jsonToolResult(output: Record<string, unknown>) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }],
    structuredContent: output,
  }
}

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
    const absRunDir = resolveRunDir(WORKTREE, run_dir)
    const contentFile = content_file ? resolveWorkspacePath(WORKTREE, content_file) : ""
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

    const scaffold = {
      run_dir: absRunDir,
      source_file: contentFile || null,
      recommended_anchor:
        contentMap?.recommended_insert_anchor ||
        stylesForLlm?.recommended_anchor ||
        inspection?.content_map?.recommended_insert_anchor ||
        null,
      body_text_style: stylesForLlm?.body_text_style || inspection?.styles_for_llm?.body_text_style || null,
      heading_map: stylesForLlm?.heading_map || inspection?.styles_for_llm?.heading_map || {},
      available_styles: stylesForLlm?.available_styles || inspection?.styles_for_llm?.available_styles || [],
      do_not_use_styles: stylesForLlm?.do_not_use_styles || inspection?.styles_for_llm?.do_not_use_styles || [],
      front_matter: contentMap?.front_matter || inspection?.content_map?.front_matter || {},
      body_placeholders: contentMap?.body_placeholders || inspection?.content_map?.body_placeholders || {},
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

process.on("uncaughtException", (error) => {
  console.error(error)
  process.exit(1)
})

process.on("unhandledRejection", (error) => {
  console.error(error)
  process.exit(1)
})

try {
  process.stdin.resume()
  await server.connect(new StdioServerTransport())
  const keepAlive = setInterval(() => {}, 60_000)
  process.on("SIGINT", async () => {
    clearInterval(keepAlive)
    await server.close()
    process.exit(0)
  })
} catch (error) {
  console.error(error)
  process.exit(1)
}
