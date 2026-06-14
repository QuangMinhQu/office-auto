import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"

// === PUBLIC API TOOLS (v3 durable workflow) ===
import { registerCreateReportTool } from "./tools/create-report"
import { registerResumeRunTool } from "./tools/resume-run"
import { registerInspectRunTool } from "./tools/inspect-run"
import { registerRetryRunTool } from "./tools/retry-run"
import { registerAbortRunTool } from "./tools/abort-run"

// === LEGACY TOOLS (deprecated, hidden with _internal_ prefix) ===
import { registerInspectTool } from "./tools/inspect"
import { registerScaffoldTool } from "./tools/scaffold"
import { registerCompilerTool } from "./tools/compiler"
import { registerValidateTool } from "./tools/validate"
import { registerExecuteTool } from "./tools/execute"
import { registerQATool } from "./tools/qa"
import { registerReviewTool } from "./tools/review"
import { registerRefreshTool } from "./tools/refresh"
import { registerOrchestratorTool } from "./tools/orchestrator"

const WORKTREE = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
const server = new McpServer({ name: "office-auto", version: "3.1.0" })

// === PUBLIC: Primary interface ===
registerCreateReportTool(server, WORKTREE)
registerResumeRunTool(server, WORKTREE)
registerInspectRunTool(server, WORKTREE)
registerRetryRunTool(server, WORKTREE)
registerAbortRunTool(server, WORKTREE)

// === INTERNAL/DEPRECATED: Low-level phase tools ===
// These are registered for backwards compatibility but should NOT be called directly.
// Agents must use createReportFromMarkdown by default.
registerInspectTool(server, WORKTREE)
registerScaffoldTool(server, WORKTREE)
registerCompilerTool(server, WORKTREE)
registerValidateTool(server, WORKTREE)
registerExecuteTool(server, WORKTREE)
registerQATool(server, WORKTREE)
registerReviewTool(server, WORKTREE)
registerRefreshTool(server, WORKTREE)
registerOrchestratorTool(server, WORKTREE)

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
