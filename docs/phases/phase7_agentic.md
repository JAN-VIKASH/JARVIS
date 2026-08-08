# Phase 7: Agentic Intelligence

## Overview
Phase 7 adds autonomous, multi-step goal planning, execution, and verification loops on top of JARVIS's cognitive reasoning and desktop automation capabilities. 

Rather than executing singular instructions directly, the agent can decompose a high-level goal into an ordered plan of dependent steps, validate them against the closed tool schema, execute them sequentially, reflect on the desktop/GUI state change to verify success, and perform recovery/retries in case of transient issues.

---

## Capabilities & Architecture
The Agentic Intelligence layer is organized under a modular design in `app/agent/`:

1. **`AgentService` (`app/agent/core.py`)**: The central entry point orchestrating goal parsing, plan execution loops, and paused confirmation handling.
2. **`PlanningEngine` (`app/agent/planner.py`)**: Uses the LLM to generate an ordered sequence of structured steps (`AgentStep`) from high-level user statements, enriched with budgeted user preferences and timeline context from `CognitiveReasoner`.
3. **`ToolSelector` (`app/agent/registry.py`)**: Validates LLM-proposed tool commands and parameter structures directly against the authoritative schemas defined in `tools/registry.py`.
4. **`ExecutionEngine` (`app/agent/executor.py`)**: Sequentially executes plan steps, verifies prerequisite completions, implements safety pre-checks, pauses for human confirmations, and transitions step states.
5. **`ReflectionEngine` (`app/agent/reflection.py`)**: Inspects GUI window lists and titles after execution to verify expected state changes (e.g. confirming that Notepad is actually active after launching).
6. **`RecoveryEngine` (`app/agent/recovery.py`)**: Manages retry bounds and refocus/recovery strategies for transient step execution errors.

```
User Request 
   │
   v
ChatService 
   │
   ├── [Classifies intent: complex_goal]
   │
   └── AgentService.execute_goal()
          │
          ├── PlanningEngine ──> Decomposes to AgentPlan
          ├── ToolSelector   ──> Validates against tools/registry.py
          │
          └── ExecutionEngine ──> Runs steps sequentially
                 │
                 ├── Safety Check (DesktopAutomationService)
                 ├── Tool Execution (DesktopAutomationService)
                 ├── ReflectionEngine (Verifies window changes)
                 └── RecoveryEngine (Retries with backoff)
```

---

## Safety Constraints
* **Closed Registries**: The agent only generates commands matching the allowed schemas in `tools/registry.py`. It cannot execute arbitrary command-line strings, bash scripts, or unregistered utilities.
* **Safety Tiering**: All executions are routed through the frozen Phase 6 `DesktopAutomationService`. Steps matching the `CONFIRMATION_REQUIRED` tier pause the agent plan loop and require the user to explicitly say "yes" to resume.
* **Timeout Hierarchy**:
  * `AGENT_TOTAL_TIMEOUT` (60s) for the entire plan execution.
  * `AGENT_STEP_TIMEOUT` (15s) for single step planning/verification.
  * `DesktopAutomationService` execution timeout (5s) for OS command execution.

---

## Baseline Synchronization
* **Phase 5 (Cognitive Intelligence Core)**: Completed (Relational profile memory, events engine, task recurrence pipelines, and context assembly).
* **Phase 6 (Desktop Automation)**: Completed (Native keyboard/mouse controls, binary allowlists, and execution safety bounds).
* **Phase 7 (Agentic Intelligence)**: Completed (Plan-execute-verify-recover agent loops).
* **Phase 8 (Browser Automation)**: Planned.
