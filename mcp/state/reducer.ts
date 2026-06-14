import type { PipelineState, PipelinePhase, ArtifactRef, CheckResult, AgentRunState, PipelineError } from "./pipeline-state"
import { createInitialState } from "./pipeline-state"
import type { PipelineEvent } from "./events"
import { loadEvents, appendEvent } from "./event-ledger"
import { assertTransitionAllowed } from "./transitions"
import { writeJsonFile, readJsonFile } from "../pipeline-core"

const SNAPSHOT_FILE = "run.json"

export function reduceEvents(events: PipelineEvent[]): PipelineState | null {
  if (events.length === 0) return null

  let state: PipelineState | null = null

  for (const event of events) {
    if (!state) {
      if (event.type !== "RunCreated") {
        throw new Error(`First event must be RunCreated, got ${event.type}`)
      }
      state = createInitialState({
        run_id: event.run_id,
        template_file: event.inputs.template_file,
        source_file: event.inputs.source_file,
        target_file: event.inputs.target_file,
        strict_mode: event.inputs.strict_mode,
      })
      state.revision = event.next_revision
      state.created_at = event.timestamp
      state.updated_at = event.timestamp
      continue
    }

    state = applyEvent(state, event)
  }

  return state
}

function applyEvent(state: PipelineState, event: PipelineEvent): PipelineState {
  const next = { ...state, updated_at: event.timestamp, revision: event.next_revision }

  switch (event.type) {
    case "RunCreated":
      break

    case "PhaseStarted":
      next.phase = event.phase
      if (event.agent) {
        next.agents = {
          ...next.agents,
          [event.agent]: {
            agent_id: event.agent,
            status: "running",
            started_at: event.timestamp,
            revision: event.next_revision,
          },
        }
      }
      break

    case "PhaseCompleted":
      next.phase = event.phase
      if (event.agent && next.agents[event.agent]) {
        next.agents = {
          ...next.agents,
          [event.agent]: {
            ...next.agents[event.agent],
            status: "completed",
            completed_at: event.timestamp,
            revision: event.next_revision,
          },
        }
      }
      break

    case "PhaseFailed":
      next.phase = event.phase
      next.status = "failed"
      next.errors = [...next.errors, event.error]
      if (event.agent && next.agents[event.agent]) {
        next.agents = {
          ...next.agents,
          [event.agent]: {
            ...next.agents[event.agent],
            status: "failed",
            completed_at: event.timestamp,
            error: event.error.message,
          },
        }
      }
      break

    case "ArtifactCreated":
      next.artifacts = {
        ...next.artifacts,
        [event.artifact.path.split("/").pop()!.replace(/\.json$/, "")]: event.artifact,
      }
      break

    case "DecisionRecorded":
      if (event.decision_type === "style_map") {
        next.decisions = { ...next.decisions, style_map: event.artifact }
      } else if (event.decision_type === "replace_range") {
        next.decisions = { ...next.decisions, replace_range: event.artifact }
      } else if (event.decision_type === "human_override") {
        next.decisions = {
          ...next.decisions,
          human_overrides: [...(next.decisions.human_overrides || []), event.artifact],
        }
      }
      break

    case "AgentAssigned":
      next.agents = {
        ...next.agents,
        [event.agent_id]: {
          agent_id: event.agent_id,
          status: "pending",
          started_at: event.timestamp,
        },
      }
      break

    case "AgentCompleted":
      if (next.agents[event.agent_id]) {
        next.agents = {
          ...next.agents,
          [event.agent_id]: {
            ...next.agents[event.agent_id],
            status: "completed",
            completed_at: event.timestamp,
          },
        }
      }
      break

    case "AgentFailed":
      if (next.agents[event.agent_id]) {
        next.agents = {
          ...next.agents,
          [event.agent_id]: {
            ...next.agents[event.agent_id],
            status: "failed",
            completed_at: event.timestamp,
            error: event.error.message,
          },
        }
      }
      break

    case "ValidationPassed":
      next.checks = { ...next.checks, [event.check_type]: event.result }
      break

    case "ValidationFailed":
      next.checks = { ...next.checks, [event.check_type]: event.result }
      break

    case "RunCompleted":
      next.phase = "complete"
      next.status = "complete"
      break

    case "RunFailed":
      next.phase = "failed"
      next.status = "failed"
      next.errors = [...next.errors, event.error]
      break

    case "RetryScheduled":
    case "HumanReviewRequested":
      break
  }

  return next
}

export async function appendAndReduce(runDir: string, event: PipelineEvent): Promise<PipelineState> {
  await appendEvent(runDir, event)

  const events = await loadEvents(runDir)
  const state = reduceEvents(events)
  if (!state) throw new Error("Failed to reduce events after append")

  await writeSnapshot(runDir, state)
  return state
}

export async function writeSnapshot(runDir: string, state: PipelineState): Promise<void> {
  await writeJsonFile(`${runDir}/${SNAPSHOT_FILE}`, state)
}

export async function loadSnapshot(runDir: string): Promise<PipelineState | null> {
  return readJsonFile(`${runDir}/${SNAPSHOT_FILE}`) ?? null
}

export async function loadOrReduce(runDir: string): Promise<PipelineState | null> {
  const events = await loadEvents(runDir)
  if (events.length === 0) {
    return loadSnapshot(runDir)
  }
  const state = reduceEvents(events)
  if (state) {
    await writeSnapshot(runDir, state)
  }
  return state
}

export { appendEvent, loadEvents }
