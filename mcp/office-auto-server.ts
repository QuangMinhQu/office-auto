import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { registerScaffoldTool } from "./tools/scaffold"
import { registerInspectTool } from "./tools/inspect"
import { registerValidateTool } from "./tools/validate"
import { registerExecuteTool } from "./tools/execute"
import { registerQATool } from "./tools/qa"
import { registerReviewTool } from "./tools/review"
import { registerRefreshTool } from "./tools/refresh"
import { registerOrchestratorTool } from "./tools/orchestrator"
import { registerCompilerTool } from "./tools/compiler"

const WORKTREE = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
const server = new McpServer({ name: "office-auto", version: "3.0.0" })

registerScaffoldTool(server, WORKTREE)
registerInspectTool(server, WORKTREE)
registerValidateTool(server, WORKTREE)
registerExecuteTool(server, WORKTREE)
registerQATool(server, WORKTREE)
registerReviewTool(server, WORKTREE)
registerRefreshTool(server, WORKTREE)
registerOrchestratorTool(server, WORKTREE)
registerCompilerTool(server, WORKTREE)

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
