"""
PlanningEngine converts a complex user goal into structured executable plan steps.
"""
import json
import re
import uuid
import time
import logging
from typing import Dict, Any, List, Optional

from app.config.settings import settings
from app.services.llm.base import BaseLLM
from app.services.llm.generation_config import GenerationConfig
from app.models.chat_models import ChatRequest
from tools.registry import get_tool_schemas
from app.agent.models import AgentPlan, AgentStep

logger = logging.getLogger("jarvis.agent.planner")

class PlanningEngine:
    """
    PlanningEngine leverages the LLM to generate a structured AgentPlan.
    """
    def __init__(self, llm: BaseLLM, cognitive_reasoner: Any):
        self.llm = llm
        self.cognitive_reasoner = cognitive_reasoner

    async def generate_plan(self, goal: str, session_id: str) -> AgentPlan:
        """
        Decomposes user goal statement into ordered executable steps with dependency prerequisites.
        """
        # 1. Fetch budgeted context using CognitiveReasoner
        try:
            contexts = await self.cognitive_reasoner.reason_over_context(
                query=goal,
                session_id=session_id,
                intent="task_query"  # generic context retrieval
            )
            context_summary = (
                f"UserProfile:\n{contexts.get('profile_context')}\n"
                f"DirectMemories:\n{contexts.get('long_term_context')}\n"
                f"Tasks:\n{contexts.get('task_context')}\n"
                f"Calendar:\n{contexts.get('timeline_context')}"
            )
        except Exception as e:
            logger.warning(f"Failed loading context for planner: {e}")
            context_summary = "No additional context found."

        # 2. Build planner prompt
        schemas = get_tool_schemas()
        schemas_str = json.dumps(schemas, indent=2)

        prompt = (
            "You are the JARVIS Agent Planner.\n"
            "Your objective is to decompose a complex goal into an ordered sequence of structured steps.\n"
            "Each step must invoke a whitelisted tool. Do not generate arbitrary command lines or bash scripts.\n\n"
            "Available Tool Schemas:\n"
            f"{schemas_str}\n\n"
            "User Preferences and System Context:\n"
            f"{context_summary}\n\n"
            "Strict JSON Output Format:\n"
            "{\n"
            '  "steps": [\n'
            "    {\n"
            '      "step_id": 1,\n'
            '      "description": "Short explanation of this step",\n'
            '      "selected_tool": "tool_name_here",\n'
            '      "parameters": {\n'
            '        "param1": "value"\n'
            "      },\n"
            '      "prerequisites": []\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. Output ONLY the raw JSON block. No explanation, markdown block wrappers, or intros.\n"
            "2. Map tools exactly to their schemas. For launching applications, use 'launch_app' with 'app_name' (notepad, chrome, vscode, explorer).\n"
            "3. Maintain dependencies: if step 2 requires step 1 to succeed first, add [1] in prerequisites.\n"
            "4. Capped at 10 steps maximum."
        )

        chat_req = ChatRequest(message=f"Generate plan for goal: '{goal}'")
        
        try:
            result = await self.llm.generate_response(
                request=chat_req,
                system_prompt=prompt,
                config=GenerationConfig(temperature=0.0)
            )
            
            resp_text = result.response.strip()
            # Clean markdown formatting wrappers if present
            if resp_text.startswith("```"):
                resp_text = re.sub(r"^```(?:json)?\n", "", resp_text)
                resp_text = re.sub(r"\n```$", "", resp_text)

            logger.info(f"LLM generated raw plan: {resp_text}")
            parsed = json.loads(resp_text)
            raw_steps = parsed.get("steps", [])
            
            steps = []
            for item in raw_steps[:10]:  # strict 10 steps limit
                step = AgentStep(
                    step_id=item.get("step_id"),
                    description=item.get("description", ""),
                    status="PENDING",
                    selected_tool=item.get("selected_tool", ""),
                    parameters=item.get("parameters", {}),
                    prerequisites=item.get("prerequisites", []),
                    retry_count=0
                )
                steps.append(step)
                
            return AgentPlan(
                plan_id=str(uuid.uuid4()),
                goal=goal,
                steps=steps,
                status="PENDING",
                created_at=time.time(),
                updated_at=time.time()
            )
        except Exception as e:
            logger.error(f"Failed parsing LLM planner response: {e}. Falling back to empty plan.")
            return AgentPlan(
                plan_id=str(uuid.uuid4()),
                goal=goal,
                steps=[],
                status="FAILED",
                created_at=time.time(),
                updated_at=time.time()
            )
