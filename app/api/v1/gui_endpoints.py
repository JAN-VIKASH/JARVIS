import os
import json
import asyncio
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse

from voice.config import voice_settings
from app.services.factory import ServiceFactory
from app.core.gui_bus import GUIEventBus

logger = logging.getLogger("jarvis.api.v1.gui_endpoints")
router = APIRouter()

# Approved list of writable GUI settings
ALLOWLIST = {
    "WAKE_WORD_ENABLED",
    "WAKE_WORD_THRESHOLD",
    "WAKE_WORD",
    "VOICE_NAME",
    "VOICE_ENABLED",
    "STT_PROVIDER",
    "TTS_PROVIDER",
    "STT_MODEL"
}

def update_env_file(updates: Dict[str, Any]) -> None:
    """
    Safely modify or append allowlisted keys in the local .env file.
    Leaves all other variables (credentials, database settings) completely untouched.
    """
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            pass

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    written_keys = set()

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            parts = stripped.split("=", 1)
            key = parts[0].strip()
            if key in ALLOWLIST and key in updates:
                val = updates[key]
                if isinstance(val, bool):
                    val_str = "True" if val else "False"
                else:
                    val_str = str(val)
                new_lines.append(f"{key}={val_str}\n")
                written_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in updates.items():
        if key in ALLOWLIST and key not in written_keys:
            if isinstance(val, bool):
                val_str = "True" if val else "False"
            else:
                val_str = str(val)
            new_lines.append(f"{key}={val_str}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

@router.get("/gui/settings", tags=["GUI API"])
async def get_gui_settings() -> Dict[str, Any]:
    """
    Returns only safe voice/GUI-related configuration settings.
    Never returns secrets, API keys, or raw .env files.
    """
    return {
        "WAKE_WORD_ENABLED": voice_settings.WAKE_WORD_ENABLED,
        "WAKE_WORD_THRESHOLD": voice_settings.WAKE_WORD_THRESHOLD,
        "WAKE_WORD": voice_settings.WAKE_WORD,
        "VOICE_NAME": voice_settings.VOICE_NAME,
        "VOICE_ENABLED": voice_settings.VOICE_ENABLED,
        "STT_PROVIDER": voice_settings.STT_PROVIDER,
        "TTS_PROVIDER": voice_settings.TTS_PROVIDER,
        "STT_MODEL": voice_settings.STT_MODEL
    }

@router.post("/gui/settings", tags=["GUI API"])
async def update_gui_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts and validates user updates against the explicit allowlist.
    Rejects unauthorized key inputs with a HTTP 400.
    """
    # 1. Validation check
    for key in updates.keys():
        if key not in ALLOWLIST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unauthorized configuration modification: key '{key}' is not allowed."
            )

    # 2. Update RAM singletons
    for key, val in updates.items():
        if hasattr(voice_settings, key):
            # Coerce value types if necessary
            target_type = type(getattr(voice_settings, key))
            if target_type == bool and isinstance(val, str):
                val = val.lower() in ("true", "1", "yes")
            elif target_type == float and isinstance(val, (int, str)):
                val = float(val)
            setattr(voice_settings, key, val)

    # 3. Persist allowlisted settings to .env
    try:
        update_env_file(updates)
    except Exception as e:
        logger.error(f"Failed to persist GUI settings to .env file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist configuration file."
        )

    # Publish updated settings event
    GUIEventBus.publish("settings_updated", updates)

    return {"status": "success", "settings": await get_gui_settings()}

@router.get("/gui/status", tags=["GUI API"])
async def get_gui_status() -> Dict[str, Any]:
    """
    Get current execution status for voice service and active plans.
    """
    voice_active = False
    voice_state = "idle"
    try:
        voice_service = ServiceFactory.get_voice_service()
        voice_active = voice_service.is_running
        voice_state = voice_service.session.conversation_state
    except Exception:
        pass

    agent_service = ServiceFactory.get_agent_service()
    plans_data = []
    for plan_id, plan in list(agent_service.active_plans.items()):
        plans_data.append({
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "status": plan.status,
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "status": s.status,
                    "selected_tool": s.selected_tool,
                    "result": s.result,
                    "error": s.error
                } for s in plan.steps
            ]
        })

    return {
        "voice_active": voice_active,
        "voice_state": voice_state,
        "wake_word_enabled": voice_settings.WAKE_WORD_ENABLED,
        "active_plans": plans_data
    }

@router.post("/gui/voice/start", tags=["GUI API"])
async def start_voice_service() -> Dict[str, Any]:
    """
    Starts the continuous voice listening service from the GUI.
    """
    try:
        voice_service = ServiceFactory.get_voice_service()
        if not voice_service.is_running:
            asyncio.create_task(voice_service.start())
            GUIEventBus.publish("voice_status", {"active": True, "state": "idle"})
        return {"status": "success", "message": "Voice service started."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start voice service: {e}"
        )

@router.post("/gui/voice/stop", tags=["GUI API"])
async def stop_voice_service() -> Dict[str, Any]:
    """
    Stops the continuous voice listening service from the GUI.
    """
    try:
        voice_service = ServiceFactory.get_voice_service()
        if voice_service.is_running:
            await voice_service.stop()
            GUIEventBus.publish("voice_status", {"active": False, "state": "idle"})
        return {"status": "success", "message": "Voice service stopped."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop voice service: {e}"
        )

@router.get("/gui/events", tags=["GUI API"])
async def stream_gui_events(request: Request) -> StreamingResponse:
    """
    SSE stream delivering real-time status transitions.
    Cleans up subscription queue immediately on client disconnect.
    """
    async def event_generator():
        queue = await GUIEventBus.subscribe()
        try:
            while True:
                # Wait for any published event
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            logger.debug("SSE client disconnected.")
        finally:
            await GUIEventBus.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
