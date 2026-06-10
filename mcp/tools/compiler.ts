import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  jsonToolResult,
  readJsonFile,
  resolveRunDir,
  resolveWorkspacePath,
  spawnPython,
  writeJsonFile,
} from "../pipeline-core"

export function registerCompilerTool(server: McpServer, worktree: string) {
  // ---- NEW: generateOpsFromSourcePacket ----
  server.registerTool(
    "generateOpsFromSourcePacket",
    {
      title: "Generate Execution Ops from Source Packet (Deterministic Compiler)",
      description:
        "Deterministic compiler: takes source_packet.json + style_map.json + replace_range.json "
        + "and produces execution_ops.json. Zero LLM involvement. Text is copied VERBATIM.",
      inputSchema: z.object({
        run_dir: z.string(),
        source_packet: z.string().optional().describe("Path to source_packet.json. Default: <run_dir>/source_packet.json"),
        style_map: z.string().optional().describe("Path to style_map.json. Default: <run_dir>/style_map.json"),
        replace_range: z.string().optional().describe("Path to replace_range.json. Default: <run_dir>/replace_range.json"),
        output: z.string().optional().describe("Output path. Default: <run_dir>/execution_ops.json"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, source_packet, style_map, replace_range, output }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)
      const args = ["--run-dir", absRunDir]

      if (source_packet) args.push("--source-packet", resolveWorkspacePath(worktree, source_packet))
      if (style_map) args.push("--style-map", resolveWorkspacePath(worktree, style_map))
      if (replace_range) args.push("--replace-range", resolveWorkspacePath(worktree, replace_range))
      if (output) args.push("--output", resolveWorkspacePath(worktree, output))

      const result = await spawnPython("source_packet_to_ops.py", args)

      const execOps = await readJsonFile(`${absRunDir}/execution_ops.json`).catch(() => ({}))
      const ops = execOps?.ops || []
      const insertCount = ops.filter((op: any) => op.op !== "remove").length
      const removeCount = ops.filter((op: any) => op.op === "remove").length

      return jsonToolResult({
        ok: result.exit_code === 0,
        run_dir: absRunDir,
        ops_count: ops.length,
        insert_ops: insertCount,
        remove_ops: removeCount,
        first_insert_anchor: execOps?.first_insert_anchor || null,
        compiled_by: execOps?.compiled_by || "source_packet_to_ops.py",
      })
    },
  )

  // ---- NEW: resolveMapping (create style_map + replace_range from defaults) ----
  server.registerTool(
    "resolveMapping",
    {
      title: "Resolve Style Mapping and Replace Range",
      description:
        "Default/deterministic mapping: creates style_map.json and replace_range.json from inspection data. "
        + "No LLM needed for known templates. Can be overridden by MapperAgent.",
      inputSchema: z.object({
        run_dir: z.string(),
        style_map_override: z.record(z.string(), z.string()).optional().describe("Override specific style mappings."),
        preserve_zones: z.array(z.string()).optional().describe("Template zones to preserve. Default: ['front_matter', 'toc', 'headers_footers']"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ run_dir, style_map_override, preserve_zones }) => {
      const absRunDir = resolveRunDir(worktree, run_dir)

      const stylesForLlm = await readJsonFile(`${absRunDir}/docx_inspect_styles_for_llm.json`).catch(() => ({}))
      const scaffold = await readJsonFile(`${absRunDir}/insert_plan_scaffold.json`).catch(() => ({}))

      const headingMap = scaffold?.heading_map || stylesForLlm?.heading_map || {}
      const bodyStyle = scaffold?.body_text_style || stylesForLlm?.body_text_style || "Normal"
      const defaultZones = preserve_zones || ["front_matter", "toc", "headers_footers"]

      const styleMap = {
        h1: headingMap.h1 || "Heading1",
        h2: headingMap.h2 || "Heading2",
        h3: headingMap.h3 || "Heading3",
        body: bodyStyle,
        caption: "Caption",
        preserve_zones: defaultZones,
        ...style_map_override,
      }

      const firstAnchor = scaffold?.CRITICAL_FIRST_OP_ANCHOR
        || scaffold?.recommended_anchor
        || ""
      const bodyParaIds: string[] = scaffold?.body_placeholders?.para_ids || []
      const removePaths = bodyParaIds
        .filter((pid: string) => pid)
        .map((pid: string) => `/body/p[@paraId=${pid}]`)

      const replaceRange = {
        insert_after_path: firstAnchor,
        remove_paths: removePaths,
        remove_rule: `Remove ${removePaths.length} body placeholders (all non-front-matter)`,
        preserve_zones: defaultZones,
      }

      await writeJsonFile(`${absRunDir}/style_map.json`, styleMap)
      await writeJsonFile(`${absRunDir}/replace_range.json`, replaceRange)

      return jsonToolResult({
        ok: true,
        run_dir: absRunDir,
        style_map: styleMap,
        replace_range: {
          insert_after_path: firstAnchor,
          remove_paths_count: removePaths.length,
          remove_rule: replaceRange.remove_rule,
        },
      })
    },
  )
}
