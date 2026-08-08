"""
Health check endpoints.
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["System"])
async def health_check():
    """
    Check API health and status.
    """
    return {
        "status": "ok",
        "assistant": "Jarvis"
    }
