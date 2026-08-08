"""
AgentService central coordinator facade.
"""
import time
import asyncio
import logging
from typing import Dict, Any, Optional

from app.services.llm.base import BaseLLM
from app.services.cognitive_reasoner import CognitiveReasoner
from app.services.desktop_automation_service import DesktopAutomationService
from app.agent.models import AgentPlan, AgentStep
from app.agent.planner import PlanningEngine
from app.agent.executor import ExecutionEngine

logger = logging.getLogger("jarvis.agent.core")

class AgentService:
    """
    Orchestrator for JARVIS Agentic Intelligence.
    Manages plan generation, execution loops, and paused confirmation states.
    """
    def __init__(self, llm: BaseLLM, cognitive_reasoner: CognitiveReasoner, 
                 desktop_service: DesktopAutomationService, browser_service: Optional[Any] = None):
        self.planner = PlanningEngine(llm, cognitive_reasoner)
        self.executor = ExecutionEngine(desktop_service, browser_service)
        self.desktop_service = desktop_service
        self.browser_service = browser_service
        self.active_plans: Dict[str, AgentPlan] = {}
        self.total_timeout = 60.0

    async def execute_goal(self, goal: str, session_id: str) -> str:
        """
        Coordinates the plan creation and sequential step-by-step execution.
        Handles paused step confirmations.
        """
        q_lower = goal.lower().strip()

        # 1. Handle confirmation replies resuming paused plans
        pending = None
        confirming_service = None
        if session_id in self.desktop_service._pending_confirmations:
            pending = self.desktop_service._pending_confirmations[session_id]
            confirming_service = self.desktop_service
        elif self.browser_service and session_id in self.browser_service._pending_confirmations:
            pending = self.browser_service._pending_confirmations[session_id]
            confirming_service = self.browser_service

        if pending:
            plan_id = pending.get("agent_plan_id")
            step_id = pending.get("agent_step_id")
            
            if plan_id and plan_id in self.active_plans:
                plan = self.active_plans[plan_id]
                step = next((s for s in plan.steps if s.step_id == step_id), None)
                
                # Check user confirmation choice
                if q_lower in ["yes", "confirm", "go ahead", "y", "okay", "proceed", "sure"]:
                    logger.info(f"User confirmed step #{step_id} in plan {plan_id}. Resuming execution.")
                    
                    cmd = pending["command"]
                    params = pending["parameters"]
                    del confirming_service._pending_confirmations[session_id]
                    
                    try:
                        step.status = "RUNNING"
                        step.start_time = time.time()
                        if confirming_service == self.browser_service:
                            result_str = await self.browser_service._run_browser_action(session_id, cmd, params)
                        else:
                            result_str = await self.desktop_service._run_tool_command(cmd, params)
                        step.end_time = time.time()
                        
                        if "error" in result_str.lower():
                            step.status = "FAILED"
                            step.error = result_str
                            plan.status = "FAILED"
                            return f"Agent execution failed at confirmed step #{step_id}: {result_str}"

                        # Verification check
                        verified = await self.executor.reflection_engine.verify_step(step.selected_tool, step.parameters, result_str)
                        if not verified:
                            step.status = "FAILED"
                            step.error = "Verification failed after user confirmation."
                            plan.status = "FAILED"
                            return f"Agent execution failed: verified state not reached for step #{step_id}."

                        step.status = "COMPLETED"
                        step.result = result_str
                    except Exception as e:
                        step.status = "FAILED"
                        step.error = str(e)
                        plan.status = "FAILED"
                        return f"Agent execution failed during confirmed step: {e}"

                    # Resume plan execution loop
                    try:
                        async with asyncio.timeout(self.total_timeout):
                            return await self.executor.execute_plan(plan, session_id)
                    except asyncio.TimeoutError:
                        plan.status = "FAILED"
                        return "Goal execution aborted: total execution timeout exceeded."

                elif q_lower in ["no", "cancel", "stop", "n", "dont", "don't"]:
                    logger.info(f"User rejected step #{step_id} in plan {plan_id}. Cancelling plan.")
                    del confirming_service._pending_confirmations[session_id]
                    if step:
                        step.status = "CANCELLED"
                        step.error = "User cancelled execution."
                    plan.status = "FAILED"
                    return "Plan execution cancelled."

        # 2. Plan a new complex goal
        logger.info(f"Initializing planning loop for new goal: '{goal}'")
        try:
            async with asyncio.timeout(self.total_timeout):
                plan = await self.planner.generate_plan(goal, session_id)
                if not plan.steps:
                    return "I could not formulate a plan to achieve that goal. Please try rephrasing."

                self.active_plans[plan.plan_id] = plan
                
                # Execute plan steps
                return await self.executor.execute_plan(plan, session_id)
        except asyncio.TimeoutError:
            return "Goal execution aborted: total execution timeout exceeded."
        except Exception as e:
            logger.error(f"Error during agentic goal execution: {e}", exc_info=True)
            return f"Error executing goal: {e}"
