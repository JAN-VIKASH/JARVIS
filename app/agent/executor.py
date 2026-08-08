"""
ExecutionEngine drives step-by-step agent loop execution.
"""
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional

from app.agent.models import AgentPlan, AgentStep
from app.agent.registry import ToolSelector
from app.agent.reflection import ReflectionEngine
from app.agent.recovery import RecoveryEngine
from app.services.desktop_automation_service import DesktopAutomationService
from tools.registry import BROWSER_TOOL_SCHEMAS

logger = logging.getLogger("jarvis.agent.executor")

class ExecutionEngine:
    """
    Executes an AgentPlan step-by-step, enforcing safety checks, prerequisites, 
    verification reflection, and recovery paths.
    """
    def __init__(self, desktop_service: DesktopAutomationService, browser_service: Any = None):
        self.desktop_service = desktop_service
        self.browser_service = browser_service
        self.tool_selector = ToolSelector()
        self.reflection_engine = ReflectionEngine(desktop_service.desktop_tool, browser_service)
        self.recovery_engine = RecoveryEngine(max_retries=3)
        self.step_timeout = 15.0

    async def execute_plan(self, plan: AgentPlan, session_id: str) -> str:
        """
        Runs the agent plan execution loop.
        Returns final status message.
        """
        plan.status = "EXECUTING"
        plan.updated_at = time.time()

        for step in plan.steps:
            # 1. Skip if already completed
            if step.status == "COMPLETED":
                continue

            # 2. Check prerequisites dependencies
            blocked = False
            for prereq_id in step.prerequisites:
                prereq_step = next((s for s in plan.steps if s.step_id == prereq_id), None)
                if not prereq_step or prereq_step.status in ("FAILED", "BLOCKED", "CANCELLED"):
                    blocked = True
                    break
                elif prereq_step.status != "COMPLETED":
                    # Dependency not done yet
                    blocked = True
                    break

            if blocked:
                step.status = "BLOCKED"
                logger.info(f"Step #{step.step_id} is BLOCKED due to prerequisites.")
                continue

            # 3. Transition to RUNNING
            step.status = "RUNNING"
            step.start_time = time.time()
            logger.info(f"Running step #{step.step_id}: {step.description}")

            # 4. Validate parameters against tool schemas
            is_valid, err = self.tool_selector.validate_tool_invocation(step.selected_tool, step.parameters)
            if not is_valid:
                step.status = "FAILED"
                step.error = err
                step.end_time = time.time()
                logger.warning(f"Step #{step.step_id} validation failed: {err}")
                plan.status = "FAILED"
                self._propagate_blocked_status(plan)
                plan.updated_at = time.time()
                return f"Agent execution failed at step #{step.step_id}: {err}"

            # 5. Safety Tier Check
            is_browser_tool = step.selected_tool in [b["name"] for b in BROWSER_TOOL_SCHEMAS]
            if is_browser_tool and self.browser_service:
                tier = self.browser_service._classify_safety_tier(step.selected_tool, step.parameters)
            else:
                tier = self.desktop_service._classify_safety_tier(step.selected_tool, step.parameters)

            if tier == "BLOCKED":
                step.status = "FAILED"
                step.error = "Safety Block: Executing this command is blocked due to safety restrictions."
                step.end_time = time.time()
                logger.warning(f"Step #{step.step_id} safety check BLOCKED.")
                plan.status = "FAILED"
                self._propagate_blocked_status(plan)
                plan.updated_at = time.time()
                return f"Agent execution failed at step #{step.step_id}: {step.error}"

            if tier == "CONFIRMATION_REQUIRED":
                # Pause plan, transition plan to WAITING_FOR_CONFIRMATION
                plan.status = "WAITING_FOR_CONFIRMATION"
                
                # Cache confirmation in correct service so we can resume
                target_service = self.browser_service if (is_browser_tool and self.browser_service) else self.desktop_service
                target_service._pending_confirmations[session_id] = {
                    "command": step.selected_tool,
                    "parameters": step.parameters,
                    "timestamp": time.time(),
                    "agent_plan_id": plan.plan_id,
                    "agent_step_id": step.step_id
                }
                
                logger.info(f"Step #{step.step_id} requires confirmation. Pausing plan.")
                return f"I need your confirmation to proceed with the action: [{step.selected_tool}] using parameters {step.parameters}. Please say 'yes' to confirm or 'no' to cancel."

            # 6. Execute step tool command with retry-loop
            await self._run_step_with_retries(step, session_id)

            step.end_time = time.time()
            if step.status == "FAILED":
                # Stop subsequent executions
                plan.status = "FAILED"
                self._propagate_blocked_status(plan)
                plan.updated_at = time.time()
                return f"Agent execution failed at step #{step.step_id}: {step.error}"

        # Check if all steps completed
        all_ok = all(s.status == "COMPLETED" for s in plan.steps)
        plan.status = "SUCCESS" if all_ok else "FAILED"
        self._propagate_blocked_status(plan)
        plan.updated_at = time.time()
        
        if plan.status == "SUCCESS":
            return "Goal completed successfully."
        else:
            return "Goal execution failed."

    def _propagate_blocked_status(self, plan: AgentPlan):
        """
        Transition any pending/running steps to BLOCKED if their prerequisites failed/blocked.
        """
        changed = True
        while changed:
            changed = False
            for step in plan.steps:
                if step.status in ("PENDING", "RUNNING"):
                    for prereq_id in step.prerequisites:
                        prereq_step = next((s for s in plan.steps if s.step_id == prereq_id), None)
                        if not prereq_step or prereq_step.status in ("FAILED", "BLOCKED", "CANCELLED"):
                            step.status = "BLOCKED"
                            changed = True
                            break

    async def _run_step_with_retries(self, step: AgentStep, session_id: str):
        """
        Helper loop running single step execution under step timeouts and recovery policies.
        """
        attempt = 0
        while attempt <= self.recovery_engine.max_retries:
            attempt += 1
            step.retry_count = attempt - 1
            
            try:
                # Step timeout constraint (15.0s)
                async with asyncio.timeout(self.step_timeout):
                    is_browser_tool = step.selected_tool in [b["name"] for b in BROWSER_TOOL_SCHEMAS]
                    if is_browser_tool and self.browser_service:
                        result_str = await self.browser_service._run_browser_action(session_id, step.selected_tool, step.parameters)
                    else:
                        result_str = await self.desktop_service._run_tool_command(step.selected_tool, step.parameters)
                    
                    if "error" in result_str.lower():
                        raise RuntimeError(result_str)

                    # 7. Verification Reflection check
                    verified = await self.reflection_engine.verify_step(step.selected_tool, step.parameters, result_str)
                    if not verified:
                        raise RuntimeError(f"Reflection verification failed. Expected state not reached. Tool output: {result_str}")

                    # Successful completion
                    step.status = "COMPLETED"
                    step.result = result_str
                    logger.info(f"Step #{step.step_id} completed successfully.")
                    return
            except Exception as e:
                err_msg = str(e)
                logger.warning(f"Step #{step.step_id} execution attempt {attempt} failed: {err_msg}")
                
                # Check if retryable
                if not self.recovery_engine.is_retryable(err_msg) or attempt > self.recovery_engine.max_retries:
                    step.status = "FAILED"
                    step.error = err_msg
                    return
                    
                # Run recovery strategy
                step.status = "RETRYING"
                await self.recovery_engine.execute_recovery_strategy(step.selected_tool, step.parameters, attempt)
