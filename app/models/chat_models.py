"""
Pydantic schemas for the chat endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """
    Schema for chat input request.
    """
    message: str = Field(..., min_length=1, description="Message to send to JARVIS")
    session_id: str = Field(default="default", description="Unique conversation session ID")
    is_voice: bool = Field(default=False, description="Flag indicating if the query is from voice interface")


class ChatResponse(BaseModel):
    """
    Schema for chat output response.
    """
    response: str = Field(..., description="Response from JARVIS")


class LLMResult(BaseModel):
    """
    Internal model representing the complete LLM execution result.
    Not exposed directly in the public API.
    """
    response: str
    provider: str
    model: str
    latency: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

