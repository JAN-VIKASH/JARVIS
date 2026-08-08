"""
Voice Session model for maintaining voice pipeline states.
"""
import uuid

class VoiceSession:
    """
    Tracks state of the active voice conversation.
    """
    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"voice_{uuid.uuid4().hex[:8]}"
        self.recording_state = False
        self.conversation_state = "idle"  # idle, listening, processing, speaking
        self.current_stt_provider = None
        self.current_tts_provider = None

    def start_recording(self):
        self.recording_state = True
        self.conversation_state = "listening"
        try:
            from app.core.gui_bus import GUIEventBus
            GUIEventBus.publish("voice_status", {"active": True, "state": "listening"})
        except Exception:
            pass

    def stop_recording(self):
        self.recording_state = False
        self.conversation_state = "processing"
        try:
            from app.core.gui_bus import GUIEventBus
            GUIEventBus.publish("voice_status", {"active": True, "state": "processing"})
        except Exception:
            pass

    def set_speaking(self):
        self.conversation_state = "speaking"
        try:
            from app.core.gui_bus import GUIEventBus
            GUIEventBus.publish("voice_status", {"active": True, "state": "speaking"})
        except Exception:
            pass

    def set_idle(self):
        self.conversation_state = "idle"
        try:
            from app.core.gui_bus import GUIEventBus
            GUIEventBus.publish("voice_status", {"active": True, "state": "idle"})
        except Exception:
            pass
