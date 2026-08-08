"""
Schemas and state representations for Agentic Intelligence.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AgentStep(BaseModel):
    """
    State and parameter specification for a single step in an agent plan.
    """
    step_id: int
    description: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, RETRYING, BLOCKED, CANCELLED, SKIPPED
    selected_tool: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    prerequisites: List[int] = Field(default_factory=list)  # step_ids that must complete first
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

class AgentPlan(BaseModel):
    """
    Collection of steps representing the goal execution path.
    """
    plan_id: str
    goal: str
    steps: List[AgentStep] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, EXECUTING, WAITING_FOR_CONFIRMATION, SUCCESS, FAILED
    created_at: float
    updated_at: float
