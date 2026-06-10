import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import {
  createRunDir,
  jsonToolResult,
  mergeJsonFile,
  readJsonFile,
  resolveRunDir,
  resolveWorkspacePath,
  safeResolvePath,
  spawnPython,
  writeJsonFile,
} from "../pipeline-core"

export function registerOrchestratorTool(server: McpServer, worktree: string) {
  // ---- NEW: runFullPipeline (deterministic compiler path, default) ----
  server.registerTool(
    "runFullPipeline",
    {
      title: "Run Full DOCX Pipeline (deterministic compiler)",
      description:
        "Orchestrate the FULL pipeline: inspect → source_packet → compile ops → strict validate → apply → QA → review → refresh → final gate. "
        + "No LLM content copying — the compiler (source_packet_to_ops.py) generates ops deterministically. "
        + "LLM only decides style_map + replace_range.",
      inputSchema: z.object({
        template_file: z.string(),
        source_file: z.string(),
        target_file: z.string().optional().describe("Output DOCX path. Default: derived from template."),
        run_dir: z.string().optional(),
        style_map: z.string().optional().describe("Path to style_map.json. If omitted, uses defaults from inspection."),
        replace_range: z.string().optional().describe("Path to replace_range.json. If omitted, uses scaffold defaults."),
        phases: z
          .array(z.enum(["inspect", "scaffold", "source_packet", "compile", "strict_validate", "apply", "qa", "review", "refresh", "final_gate"]))
          .default(["inspect", "scaffold", "source_packet", "compile", "strict_validate", "apply", "qa", "review", "refresh", "final_gate"]),
        strict: z.boolean().default(true).describe("If true, hard-block apply on validation failure"),
      }),
      annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ template_file, source_file, target_file, run_dir, style_map, replace_range, phases, strict }) => {
      const absTpl = resolveWorkspacePath(worktree, template_file)
      const absSrc = resolveWorkspacePath(worktree, source_file)
      const absRunDir = run_dir
        ? resolveRunDir(worktree, run_dir)
        : await createRunDir(worktree, absTpl)
      const absTarget = target_file
        ? resolveWorkspacePath(worktree, target_file)
        : absTpl.replace(/_template/, "").replace(/\.docx$/, "_output.docx")

      const checkpoints: Record<string, any> = {}

      // Write initial run.json (atomic state machine)
      await writeJsonFile(`${absRunDir}/run.json`, {
        run_id: absRunDir.split("/").pop(),
        phase: "created",
        pipeline_version: "3",
        template_file: absTpl,
        source_file: absSrc,
        target_file: absTarget,
        strict_mode: strict,
        artifacts: {},
        final_gate: { passed: false },
      })

      // ---- Phase 1: Inspect (deterministic, no LLM) ----
      if (phases.includes("inspect")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "inspecting" })

        const inspectResult = await spawnPython("docx_inspect.py", [
          "--template-file", absTpl,
          "--run-dir", absRunDir,
        ])

        if (inspectResult.exit_code !== 0) {
          return jsonToolResult({
            ok: false, phase: "inspect",
            error: "Inspection failed", stderr: inspectResult.stderr,
            checkpoints, run_dir: absRunDir,
          })
        }

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: "inspected",
          artifacts: { docx_inspect_output: `${absRunDir}/docx_inspect_output.json` },
        })
        checkpoints.inspect = { ok: true }
      }

      // ---- Phase 2: Scaffold (deterministic aggregation) ----
      if (phases.includes("scaffold")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "scaffolding" })

        await spawnPython("docx_inspect.py", [
          "--template-file", absTpl,
          "--run-dir", absRunDir,
        ])

        // Build scaffold from inspection (done by prepareInsertPlan MCP logic)
        const scaffold = await buildScaffold(worktree, absRunDir, absSrc)
        await writeJsonFile(`${absRunDir}/insert_plan_scaffold.json`, scaffold)

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: "scaffolded",
          artifacts: { insert_plan_scaffold: `${absRunDir}/insert_plan_scaffold.json` },
        })
        checkpoints.scaffold = { ok: true }
      }

      // ---- Phase 3: Source Packet (deterministic markdown parser) ----
      if (phases.includes("source_packet")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "source_packeting" })

        const packetResult = await spawnPython("source_packet.py", [
          "--source", absSrc,
          "--run-dir", absRunDir,
        ])

        if (packetResult.exit_code !== 0) {
          return jsonToolResult({
            ok: false, phase: "source_packet",
            error: "Source packet failed", stderr: packetResult.stderr,
            checkpoints, run_dir: absRunDir,
          })
        }

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: "source_packeted",
          artifacts: { source_packet: `${absRunDir}/source_packet.json` },
        })
        checkpoints.source_packet = { ok: true }
      }

      // ---- Phase 4: Compile ops (deterministic compiler) ----
      if (phases.includes("compile")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "compiling" })

        const compileArgs = [
          "--run-dir", absRunDir,
          "--source-packet", `${absRunDir}/source_packet.json`,
        ]

        if (style_map) {
          compileArgs.push("--style-map", resolveWorkspacePath(worktree, style_map))
        }
        if (replace_range) {
          compileArgs.push("--replace-range", resolveWorkspacePath(worktree, replace_range))
        }

        const compileResult = await spawnPython("source_packet_to_ops.py", compileArgs)

        if (compileResult.exit_code !== 0) {
          return jsonToolResult({
            ok: false, phase: "compile",
            error: "Compilation failed", stderr: compileResult.stderr,
            checkpoints, run_dir: absRunDir,
          })
        }

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: "compiled",
          artifacts: { execution_ops: `${absRunDir}/execution_ops.json` },
        })
        checkpoints.compile = { ok: true }
      }

      // ---- Phase 5: Strict Validate (HARD BLOCK on high severity) ----
      if (phases.includes("strict_validate")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "validating" })

        const validateResult = await spawnPython("validate_ops_strict.py", [
          "--run-dir", absRunDir,
          "--ops-file", `${absRunDir}/execution_ops.json`,
        ])

        const strictReport = await readJsonFile(`${absRunDir}/strict_validation.json`).catch(() => ({}))
        const valid = strictReport?.valid === true

        checkpoints.strict_validate = {
          ok: validateResult.exit_code === 0,
          valid,
          blocking_error_count: strictReport?.high_severity_count || 0,
          warning_count: strictReport?.warning_count || 0,
        }

        if (!valid && strict) {
          return jsonToolResult({
            ok: false,
            phase: "strict_validate",
            error: "Validation failed with blocking errors",
            blocking_errors: strictReport?.blocking_errors || [],
            checkpoints,
            run_dir: absRunDir,
          })
        }

        // Also run warn-only validator for planning_report
        await spawnPython("docx_validate_ops.py", [
          "--run-dir", absRunDir,
          "--ops-file", `${absRunDir}/execution_ops.json`,
        ])

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: strict ? "validated_strict" : "validated",
          artifacts: {
            strict_validation: `${absRunDir}/strict_validation.json`,
            execution_ops_validation: `${absRunDir}/execution_ops_validation.json`,
          },
        })
      }

      // ---- Phase 6: Apply (deterministic executor) ----
      if (phases.includes("apply")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "applying" })

        const applyResult = await spawnPython("execute_execution_ops.py", [
          "--run-dir", absRunDir,
          "--target-file", absTarget,
        ])

        const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => ({}))
        const buildStatus = opsReport?.failed === 0 ? "completed" : "partial"

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: buildStatus === "completed" ? "built" : "build_partial",
          target_file: absTarget,
          artifacts: { execute_ops_report: `${absRunDir}/execute_ops_report.json` },
        })

        checkpoints.apply = {
          ok: applyResult.exit_code === 0,
          build_status: buildStatus,
          ops_applied: opsReport?.succeeded || 0,
          ops_failed: opsReport?.failed || 0,
        }

        if (buildStatus !== "completed") {
          return jsonToolResult({
            ok: false, phase: "apply",
            error: `Build ${buildStatus}: ${opsReport?.failed || 0} ops failed`,
            checkpoints, run_dir: absRunDir,
          })
        }
      }

      // ---- Phase 7: QA ----
      if (phases.includes("qa")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "qa" })
        await spawnPython("qa_docx.py", ["--run-dir", absRunDir])
        const qaReport = await readJsonFile(`${absRunDir}/qa_report.json`).catch(() => null)
        checkpoints.qa = { ok: !!qaReport }
      }

      // ---- Phase 8: Review ----
      if (phases.includes("review")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "reviewing" })
        await spawnPython("review_docx.py", ["--run-dir", absRunDir])
        const reviewReport = await readJsonFile(`${absRunDir}/review_report.json`).catch(() => null)
        checkpoints.review = { ok: !!reviewReport, passed: reviewReport?.passed }
      }

      // ---- Phase 9: Refresh TOC ----
      if (phases.includes("refresh")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "refreshing" })
        const refreshResult = await spawnPython("docx_refresh_fields.py", [
          "--target-file", absTarget,
          "--strategy", "auto",
          "--run-dir", absRunDir,
        ])
        checkpoints.refresh = {
          ok: refreshResult.exit_code === 0,
          strategy: refreshResult.stdout_json?.strategy_used || "auto",
        }
      }

      // ---- Phase 10: Final Gate (CODE-LEVEL, not prompt-based) ----
      if (phases.includes("final_gate")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "final_gate" })

        const gateResult = await spawnPython("final_gate.py", [
          "--run-dir", absRunDir,
        ])

        const gateReport = await readJsonFile(`${absRunDir}/final_gate.json`).catch(() => ({}))
        const gatePassed = gateReport?.passed === true

        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: gatePassed ? "complete" : "failed_final_gate",
          final_gate: { passed: gatePassed },
        })

        checkpoints.final_gate = {
          ok: gateResult.exit_code === 0,
          passed: gatePassed,
          failed_checks: gateReport?.failed_checks || [],
          missing_artifacts: gateReport?.missing_artifacts || [],
        }

        if (!gatePassed) {
          return jsonToolResult({
            ok: false,
            phase: "final_gate",
            error: `Final gate failed: ${(gateReport?.failed_checks || []).join(", ")}`,
            gate_report: gateReport,
            checkpoints,
            run_dir: absRunDir,
            target_file: absTarget,
          })
        }
      }

      return jsonToolResult({
        ok: true,
        run_dir: absRunDir,
        target_file: absTarget,
        checkpoints,
        message: `Pipeline complete. Report: ${absTarget}`,
      })
    },
  )

  // ---- LEGACY: runPipelineFromOps (for backward compatibility) ----
  server.registerTool(
    "runPipelineFromOps",
    {
      title: "Run DOCX Pipeline from existing ops file (legacy)",
      description:
        "Run pipeline phases starting from an existing execution_ops.json. "
        + "DEPRECATED: Prefer runFullPipeline which auto-generates ops via deterministic compiler.",
      inputSchema: z.object({
        template_file: z.string(),
        ops_file: z.string().describe("Path to execution_ops.json"),
        source_file: z.string().optional(),
        run_dir: z.string().optional(),
        phases: z
          .array(z.enum(["inspect", "validate", "apply", "qa", "review", "refresh"]))
          .default(["inspect", "validate", "apply", "qa", "review"]),
      }),
      annotations: { readOnlyHint: false, idempotentHint: false, openWorldHint: false },
    },
    async ({ template_file, ops_file, source_file, run_dir, phases }) => {
      const absTpl = resolveWorkspacePath(worktree, template_file)
      const absRunDir = run_dir
        ? resolveRunDir(worktree, run_dir)
        : await createRunDir(worktree, absTpl)
      const absOpsFile = resolveWorkspacePath(worktree, ops_file)

      const checkpoints: Record<string, any> = {}
      let currentTarget = absTpl.replace(/_template/, "").replace(/\.docx$/, "_output.docx")

      await writeJsonFile(`${absRunDir}/run.json`, {
        template_file: absTpl,
        target_file: currentTarget,
        source_file: source_file ? resolveWorkspacePath(worktree, source_file) : undefined,
        pipeline_version: "2",
        phase: "created",
      })

      if (phases.includes("inspect")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "inspecting" })
        const inspectResult = await spawnPython("docx_inspect.py", [
          "--template-file", absTpl, "--run-dir", absRunDir,
        ])
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "inspected" })
        checkpoints.inspect = { ok: inspectResult.exit_code === 0 }
        if (inspectResult.exit_code !== 0) {
          return jsonToolResult({
            ok: false, phase: "inspect", error: "Inspection failed",
            stderr: inspectResult.stderr, checkpoints, run_dir: absRunDir,
          })
        }
      }

      if (phases.includes("validate")) {
        // Run strict validator (hard block on high severity)
        await spawnPython("validate_ops_strict.py", [
          "--run-dir", absRunDir, "--ops-file", absOpsFile,
        ])
        const strictReport = await readJsonFile(`${absRunDir}/strict_validation.json`).catch(() => ({}))
        const hasHighSeverity = strictReport?.valid === false

        // Also run warn-only for planning_report
        await spawnPython("docx_validate_ops.py", [
          "--run-dir", absRunDir, "--ops-file", absOpsFile,
        ])
        const validationReport = await readJsonFile(`${absRunDir}/execution_ops_validation.json`).catch(() => ({}))

        checkpoints.validate = {
          ok: !hasHighSeverity,
          valid: !hasHighSeverity,
          blocking_errors: strictReport?.blocking_errors || [],
          warning_count: validationReport?.warnings?.length || 0,
        }

        if (hasHighSeverity) {
          return jsonToolResult({
            ok: false, phase: "validate",
            error: "Validation failed with blocking errors",
            blocking_errors: strictReport?.blocking_errors,
            checkpoints, run_dir: absRunDir,
          })
        }

        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "validated" })
      }

      if (phases.includes("apply")) {
        await mergeJsonFile(`${absRunDir}/run.json`, { phase: "applying" })
        const applyResult = await spawnPython("execute_execution_ops.py", [
          "--run-dir", absRunDir, "--target-file", currentTarget,
        ])
        const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => ({}))
        await mergeJsonFile(`${absRunDir}/run.json`, {
          phase: applyResult.exit_code === 0 ? "built" : "failed",
          target_file: currentTarget,
        })
        checkpoints.apply = {
          ok: applyResult.exit_code === 0,
          ops_applied: opsReport?.succeeded || 0,
          ops_failed: opsReport?.failed || 0,
        }
      }

      if (phases.includes("qa")) {
        await spawnPython("qa_docx.py", ["--run-dir", absRunDir])
        const qaReport = await readJsonFile(`${absRunDir}/qa_report.json`).catch(() => null)
        checkpoints.qa = { ok: !!qaReport }
      }

      if (phases.includes("review")) {
        await spawnPython("review_docx.py", ["--run-dir", absRunDir])
        const reviewReport = await readJsonFile(`${absRunDir}/review_report.json`).catch(() => null)
        checkpoints.review = { ok: !!reviewReport, passed: reviewReport?.passed }
      }

      if (phases.includes("refresh")) {
        const refreshResult = await spawnPython("docx_refresh_fields.py", [
          "--target-file", currentTarget, "--strategy", "auto", "--run-dir", absRunDir,
        ])
        checkpoints.refresh = { ok: refreshResult.exit_code === 0 }
      }

      // Run final gate
      await spawnPython("final_gate.py", ["--run-dir", absRunDir])
      const gateReport = await readJsonFile(`${absRunDir}/final_gate.json`).catch(() => ({}))
      const gatePassed = gateReport?.passed === true

      return jsonToolResult({
        ok: gatePassed,
        run_dir: absRunDir,
        target_file: currentTarget,
        checkpoints,
        final_gate: gateReport,
      })
    },
  )
}

// ---- Helper: build scaffold from inspection (used internally) ----
async function buildScaffold(worktree: string, absRunDir: string, sourceFile: string): Promise<Record<string, unknown>> {
  const { parseMarkdownHeadings, readJsonFile, readTextFile } = await import("../pipeline-core")

  const inspection = await readJsonFile(`${absRunDir}/docx_inspect_output.json`).catch(() => ({}))
  const stylesForLlm = await readJsonFile(`${absRunDir}/docx_inspect_styles_for_llm.json`).catch(() => ({}))
  const contentMap = await readJsonFile(`${absRunDir}/docx_inspect_content_map.json`).catch(() => ({}))

  let headings: Array<{ level: number; text: string }> = []
  try {
    const markdownText = await readTextFile(sourceFile)
    headings = parseMarkdownHeadings(markdownText)
  } catch { /* ignore */ }

  const rawAnchor = contentMap?.recommended_insert_anchor
    || stylesForLlm?.recommended_anchor
    || inspection?.content_map?.recommended_insert_anchor
    || null

  const bodyPlaceholders = contentMap?.body_placeholders || inspection?.content_map?.body_placeholders || {}
  const bodyParaIds: string[] = Array.isArray(bodyPlaceholders.para_ids) ? bodyPlaceholders.para_ids : []

  return {
    run_dir: absRunDir,
    source_file: sourceFile,
    recommended_anchor: rawAnchor ? `/body/p[@paraId=${rawAnchor}]` : null,
    CRITICAL_FIRST_OP_ANCHOR: rawAnchor ? `/body/p[@paraId=${rawAnchor}]` : null,
    toc_last_para_id: inspection?.front_matter_boundary?.last_para_id || null,
    front_matter_last_para_id: inspection?.front_matter_boundary?.last_para_id || null,
    body_text_style: stylesForLlm?.body_text_style || inspection?.styles_for_llm?.body_text_style || null,
    heading_map: stylesForLlm?.heading_map || inspection?.styles_for_llm?.heading_map || {},
    available_styles: (stylesForLlm?.available_styles || inspection?.styles_for_llm?.available_styles || []).map((s: any) => ({
      style_id: s.style_id, name: s.name, outline_level: s.outline_level,
    })),
    do_not_use_styles: stylesForLlm?.do_not_use_styles || [],
    body_placeholders: {
      para_ids: bodyParaIds,
      total_count: bodyParaIds.length,
      remove_op_required: true,
      details: (inspection?.all_para_ids || [])
        .filter((p: any) => !p.is_front_matter && bodyParaIds.includes(p.para_id))
        .map((p: any) => ({
          paraId: p.para_id,
          text_preview: (p.text_preview || "").slice(0, 60),
          is_front_matter: p.is_front_matter || false,
          style_name: p.style_name || null,
        })),
    },
    markdown_headings: headings,
    markdown_heading_count: headings.length,
  }
}
