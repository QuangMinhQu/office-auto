import type { PipelineState, PipelinePhase } from "../state/pipeline-state"
import type { PipelineEvent } from "../state/events"
import { generateEventId } from "../state/events"
import { createInitialState } from "../state/pipeline-state"
import { appendAndReduce, loadOrReduce, loadEvents, reduceEvents, writeSnapshot } from "../state/reducer"
import { assertTransitionAllowed, isTerminalPhase } from "../state/transitions"
import { route } from "./router"
import { canRetry, getRetryConfig, computeBackoff } from "./retry-policy"
import { acquireRunLock, releaseRunLock } from "../state/lock"
import {
  createRunDir,
  resolveWorkspacePath,
} from "../pipeline-core"

import { TemplateInspectorAgent } from "../agents/template-inspector-agent"
import { SourceParserAgent } from "../agents/source-parser-agent"
import { MapperAgent } from "../agents/mapper-agent"
import { CompilerAgent } from "../agents/compiler-agent"
import { ValidatorAgent } from "../agents/validator-agent"
import { ExecutorAgent } from "../agents/executor-agent"
import { VerifierAgent } from "../agents/verifier-agent"
import { QAAgent } from "../agents/qa-agent"
import { ReviewerAgent } from "../agents/reviewer-agent"
import { PostProcessorAgent } from "../agents/postprocessor-agent"
import { FinalGateAgent } from "../agents/final-gate-agent"
import type { BaseAgent, AgentTask } from "../agents/base"

export interface SupervisorOptions {
  template_file: string
  source_file: string
  target_file?: string
  run_dir?: string
  style_map?: string
  replace_range?: string
  strict?: boolean
  require_review?: boolean
  log_level?: "brief" | "normal" | "debug"
}

export interface SupervisorResult {
  ok: boolean
  run_id: string
  run_dir: string
  target_file?: string
  phase: PipelinePhase
  status: string
  summary: {
    source_blocks?: number
    ops_count?: number
    final_gate_passed?: boolean
  }
  debug?: {
    artifacts: Record<string, string>
    failed_checks?: string[]
  }
  user_log: string[]
}

export class PipelineSupervisor {
  private worktree: string
  private agents: Map<string, BaseAgent>

  constructor(worktree: string) {
    this.worktree = worktree
    this.agents = new Map()

    const agents: BaseAgent[] = [
      new TemplateInspectorAgent(worktree),
      new SourceParserAgent(worktree),
      new MapperAgent(worktree),
      new CompilerAgent(worktree),
      new ValidatorAgent(worktree),
      new ExecutorAgent(worktree),
      new VerifierAgent(worktree),
      new QAAgent(worktree),
      new ReviewerAgent(worktree),
      new PostProcessorAgent(worktree),
      new FinalGateAgent(worktree),
    ]

    for (const agent of agents) {
      this.agents.set(agent.agentId, agent)
    }
  }

  async execute(opts: SupervisorOptions): Promise<SupervisorResult> {
    const userLog: string[] = []
    const absTpl = resolveWorkspacePath(this.worktree, opts.template_file)
    const absSrc = resolveWorkspacePath(this.worktree, opts.source_file)
    const absRunDir = opts.run_dir
      ? resolveWorkspacePath(this.worktree, opts.run_dir)
      : await createRunDir(this.worktree, absTpl)
    const absTarget = opts.target_file
      ? resolveWorkspacePath(this.worktree, opts.target_file)
      : absTpl.replace(/_template/, "").replace(/\.docx$/, "_output.docx")
    const strict = opts.strict ?? true

    const lock = await acquireRunLock(absRunDir, "supervisor")
    if (!lock) {
      return {
        ok: false,
        run_id: absRunDir.split("/").pop() || "unknown",
        run_dir: absRunDir,
        target_file: absTarget,
        phase: "failed",
        status: "failed",
        summary: {},
        user_log: ["Run directory is locked by another process"],
      }
    }

    try {
      const existingState = await loadOrReduce(absRunDir)

      if (existingState && isTerminalPhase(existingState.phase)) {
        userLog.push(`Run already complete (phase: ${existingState.phase})`)
        return this.buildResult(existingState, absRunDir, absTarget, userLog)
      }

      // Pre-load style_map/replace_range if provided via opts
      if (opts.style_map || opts.replace_range) {
        // These will be picked up by the compiler agent via state.decisions
      }

      const events = await this.runLoop(existingState, absRunDir, {
        template_file: absTpl,
        source_file: absSrc,
        target_file: absTarget,
        strict,
        require_review: opts.require_review ?? false,
      }, userLog)

      const finalState = reduceEvents(events)
      if (!finalState) {
        throw new Error("Failed to reduce final state from events")
      }

      return this.buildResult(finalState, absRunDir, absTarget, userLog)
    } finally {
      await releaseRunLock(absRunDir)
    }
  }

  private async runLoop(
    existingState: PipelineState | null,
    runDir: string,
    inputs: {
      template_file: string
      source_file: string
      target_file: string
      strict: boolean
      require_review: boolean
    },
    userLog: string[],
  ): Promise<PipelineEvent[]> {
    const events: PipelineEvent[] = []

    // Initialize if no existing state
    let state: PipelineState
    const runId = runDir.split("/").pop() || "auto"

    if (!existingState || existingState.phase === "created") {
      const runCreated: PipelineEvent = {
        event_id: generateEventId(),
        run_id: runId,
        type: "RunCreated",
        inputs: {
          template_file: inputs.template_file,
          source_file: inputs.source_file,
          target_file: inputs.target_file,
          strict_mode: inputs.strict,
        },
        timestamp: new Date().toISOString(),
        prev_revision: 0,
        next_revision: 1,
      }

      events.push(runCreated)
      state = createInitialState({
        run_id: runId,
        template_file: inputs.template_file,
        source_file: inputs.source_file,
        target_file: inputs.target_file,
        strict_mode: inputs.strict,
      })
      state.revision = 1
      userLog.push(`Run ${runId} created`)
    } else {
      state = existingState
      userLog.push(`Resuming run ${runId} from phase: ${state.phase}`)
    }

    // Main supervise loop
    let retryCount = 0
    const phaseRetries: Record<string, number> = {}

    while (!isTerminalPhase(state.phase)) {
      const decision = route(state)
      if (!decision || !decision.canProceed) break

      const nextPhase = decision.phase
      assertTransitionAllowed(state.phase, nextPhase)

      const agent = this.agents.get(decision.agent)
      if (!agent) {
        userLog.push(`Error: No agent found for ${decision.agent}`)
        break
      }

      // Phase started
      const phaseStartEvent: PipelineEvent = {
        event_id: generateEventId(),
        run_id: runId,
        type: "PhaseStarted",
        phase: nextPhase,
        agent: decision.agent,
        timestamp: new Date().toISOString(),
        prev_revision: state.revision,
        next_revision: state.revision + 1,
      }
      events.push(phaseStartEvent)

      const task: AgentTask = {
        run_id: runId,
        task_id: `${runId}_${nextPhase}_${state.revision}`,
        phase: nextPhase,
        run_dir: runDir,
        input_state_revision: state.revision,
        required_artifacts: decision.required_artifacts,
        output_artifacts: [],
        idempotency_key: `${runId}_${nextPhase}`,
      }

      const result = await agent.execute(task, state)

      if (result.ok) {
        for (const e of result.events) {
          events.push(e)
        }

        const phaseEndEvent: PipelineEvent = {
          event_id: generateEventId(),
          run_id: runId,
          type: "PhaseCompleted",
          phase: nextPhase,
          agent: decision.agent,
          timestamp: new Date().toISOString(),
          prev_revision: result.events.length > 0
            ? result.events[result.events.length - 1].next_revision
            : state.revision + 1,
          next_revision: result.events.length > 0
            ? result.events[result.events.length - 1].next_revision + 1
            : state.revision + 2,
        }
        events.push(phaseEndEvent)

        const shortPhase = nextPhase.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
        userLog.push(`${shortPhase.charAt(0).toUpperCase() + shortPhase.slice(1)}: ${result.summary || "OK"}`)
        retryCount = 0
        delete phaseRetries[nextPhase]
      } else {
        const phaseRetryCount = phaseRetries[nextPhase] || 0
        const retryable = canRetry(nextPhase, phaseRetryCount, result.error?.code)

        if (retryable) {
          phaseRetries[nextPhase] = (phaseRetries[nextPhase] || 0) + 1
          const config = getRetryConfig(nextPhase)
          const delay = computeBackoff(phaseRetries[nextPhase], config)

          const retryEvent: PipelineEvent = {
            event_id: generateEventId(),
            run_id: runId,
            type: "RetryScheduled",
            phase: nextPhase,
            agent_id: decision.agent,
            attempt: phaseRetries[nextPhase],
            max_attempts: config.max_attempts,
            timestamp: new Date().toISOString(),
            prev_revision: state.revision,
            next_revision: state.revision + 1,
          }
          events.push(retryEvent)
          userLog.push(`Retrying ${nextPhase} (attempt ${phaseRetries[nextPhase]}/${config.max_attempts}) in ${delay}ms`)

          await new Promise((resolve) => setTimeout(resolve, delay))
          state = reduceEvents(events) || state
          continue
        }

        const failedEvent: PipelineEvent = {
          event_id: generateEventId(),
          run_id: runId,
          type: "RunFailed",
          failed_phase: nextPhase,
          error: result.error || {
            phase: nextPhase,
            agent: decision.agent,
            message: `Phase ${nextPhase} failed`,
            timestamp: new Date().toISOString(),
            recoverable: false,
          },
          timestamp: new Date().toISOString(),
          prev_revision: state.revision,
          next_revision: state.revision + 1,
        }
        events.push(failedEvent)

        for (const e of result.events) {
          events.push(e)
        }

        userLog.push(`Failed at ${nextPhase}: ${result.error?.message || "Unknown error"}`)
        break
      }

      // Rebuild state from all events
      state = reduceEvents(events) || state

      // Persist snapshot
      if (state) {
        await writeSnapshot(runDir, state)
      }
    }

    return events
  }

  private buildResult(
    state: PipelineState,
    runDir: string,
    targetFile: string,
    userLog: string[],
  ): SupervisorResult {
    return {
      ok: state.status === "complete",
      run_id: state.run_id,
      run_dir: runDir,
      target_file: targetFile,
      phase: state.phase,
      status: state.status,
      summary: {
        source_blocks: state.artifacts.source_packet ? undefined : undefined,
        ops_count: undefined,
        final_gate_passed: state.checks.final_gate?.passed ?? false,
      },
      debug: {
        artifacts: Object.fromEntries(
          Object.entries(state.artifacts).map(([k, v]) => [k, v.path]),
        ),
        failed_checks: state.checks.final_gate?.errors || [],
      },
      user_log: userLog,
    }
  }
}
