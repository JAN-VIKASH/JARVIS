"""
Chat routing interface.
"""

from fastapi import APIRouter, Depends
from app.models.chat_models import ChatRequest, ChatResponse
from app.services.interfaces.base_chat_service import BaseChatService
from app.services.factory import ServiceFactory

router = APIRouter()

def get_chat_service() -> BaseChatService:
    """
    Dependency injection provider for BaseChatService.
    """
    return ServiceFactory.get_chat_service()

@router.post("/chat", response_model=ChatResponse, tags=["AI Response"])
async def chat_endpoint(
    request: ChatRequest,
    chat_service: BaseChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Endpoint to receive messages and return the assistant response.
    Delegates execution to ChatService.
    """
    response_text = await chat_service.execute_chat(request)
    return ChatResponse(response=response_text)
