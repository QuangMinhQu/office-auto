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
} from "../pipeline-core"

export function registerOrchestratorTool(server: McpServer, worktree: string) {
  server.registerTool(
    "runFullPipeline",
    {
      title: "Run Full DOCX Pipeline",
      description:
        "Orchestrate: inspect → validate → apply → QA → review → refreshFields. Returns checkpoint after each phase.",
      inputSchema: z.object({
        template_file: z.string(),
        ops_file: z.string().describe("Path to execution_ops.json that the LLM has created"),
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
      let currentTarget = ""

      // Phase: inspect
      if (phases.includes("inspect")) {
        const targetFile = absTpl.replace(/_template/, "").replace(/\.docx$/, "_output.docx")
        currentTarget = targetFile

        await mergeJsonFile(`${absRunDir}/run.json`, {
          template_file: absTpl,
          target_file: targetFile,
          source_file: source_file ? resolveWorkspacePath(worktree, source_file) : undefined,
          status: "inspecting",
        })

        const inspectResult = await spawnPython("docx_inspect.py", [
          "--template-file", absTpl,
          "--run-dir", absRunDir,
        ])

        await mergeJsonFile(`${absRunDir}/run.json`, { status: "inspected" })
        checkpoints.inspect = { ok: inspectResult.exit_code === 0, exit_code: inspectResult.exit_code }

        if (inspectResult.exit_code !== 0) {
          return jsonToolResult({
            ok: false,
            phase: "inspect",
            error: "Inspection failed",
            stderr: inspectResult.stderr,
            checkpoints,
            run_dir: absRunDir,
          })
        }
      }

      // Phase: validate
      if (phases.includes("validate")) {
        const validateResult = await spawnPython("docx_validate_ops.py", [
          "--run-dir", absRunDir,
          "--ops-file", absOpsFile,
        ])
        const validationReport = await readJsonFile(`${absRunDir}/execution_ops_validation.json`).catch(() => ({}))
        const hasHighSeverity = validationReport?.warnings?.some((w: any) => w.severity === "high")

        checkpoints.validate = {
          ok: validateResult.exit_code === 0,
          valid: !hasHighSeverity,
          warning_count: validationReport?.warnings?.length || 0,
          high_severity_count: validationReport?.high_severity_count || 0,
        }

        if (!hasHighSeverity) {
          await mergeJsonFile(`${absRunDir}/run.json`, { status: "validated" })
        }
      }

      // Phase: apply
      if (phases.includes("apply")) {
        const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
        const resolvedTarget = safeResolvePath([currentTarget, runJson?.target_file])

        if (!resolvedTarget) {
          return jsonToolResult({
            ok: false,
            phase: "apply",
            error: "target_file not resolved",
            checkpoints,
            run_dir: absRunDir,
          })
        }

        currentTarget = resolvedTarget
        await mergeJsonFile(`${absRunDir}/run.json`, {
          target_file: resolvedTarget,
          status: "executing",
        })

        const applyResult = await spawnPython("execute_execution_ops.py", [
          "--run-dir", absRunDir,
          "--target-file", resolvedTarget,
        ])
        const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => ({}))
        await mergeJsonFile(`${absRunDir}/run.json`, {
          status: applyResult.exit_code === 0 ? "built" : "failed",
        })

        checkpoints.apply = {
          ok: applyResult.exit_code === 0,
          ops_applied: opsReport?.succeeded || 0,
          ops_failed: opsReport?.failed || 0,
        }
      }

      // Phase: qa
      if (phases.includes("qa")) {
        const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
        const resolvedTarget = safeResolvePath([currentTarget, runJson?.target_file, runJson?.artifacts?.target_file])

        if (resolvedTarget) {
          await mergeJsonFile(`${absRunDir}/run.json`, { target_file: resolvedTarget })
          await spawnPython("qa_docx.py", ["--run-dir", absRunDir])
          const qaReport = await readJsonFile(`${absRunDir}/qa_report.json`).catch(() => null)
          checkpoints.qa = { ok: !!qaReport, hasReport: !!qaReport }
        } else {
          checkpoints.qa = { ok: false, error: "target_file not found for QA" }
        }
      }

      // Phase: review
      if (phases.includes("review")) {
        const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
        const resolvedTarget = safeResolvePath([currentTarget, runJson?.target_file])

        if (resolvedTarget) {
          await mergeJsonFile(`${absRunDir}/run.json`, { target_file: resolvedTarget })
          await spawnPython("review_docx.py", ["--run-dir", absRunDir])
          const reviewReport = await readJsonFile(`${absRunDir}/review_report.json`).catch(() => null)
          checkpoints.review = { ok: !!reviewReport, hasReport: !!reviewReport }
        } else {
          checkpoints.review = { ok: false, error: "target_file not found for review" }
        }
      }

      // Phase: refresh
      if (phases.includes("refresh")) {
        const runJson = await readJsonFile(`${absRunDir}/run.json`).catch(() => ({}))
        const resolvedTarget = safeResolvePath([currentTarget, runJson?.target_file])

        if (resolvedTarget) {
          const refreshResult = await spawnPython("docx_refresh_fields.py", [
            "--target-file", resolvedTarget,
            "--strategy", "auto",
            "--run-dir", absRunDir,
          ])
          checkpoints.refresh = {
            ok: refreshResult.exit_code === 0,
            strategy_used: refreshResult.stdout_json?.strategy_used || refreshResult.stdout_json?.method,
          }
        } else {
          checkpoints.refresh = { ok: false, error: "target_file not found for field refresh" }
        }
      }

      return jsonToolResult({
        ok: true,
        run_dir: absRunDir,
        target_file: currentTarget,
        checkpoints,
      })
    },
  )
}
