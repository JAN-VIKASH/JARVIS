"""
Voice Controller script to launch and manage the Push-to-Talk VoiceService turn-taking interface.
"""
import asyncio
import sys
from voice.config import voice_settings
from voice.logger import voice_logger
from voice.session import VoiceSession
from voice.providers.stt_factory import STTProviderFactory
from voice.providers.tts_factory import TTSProviderFactory
from app.services.factory import ServiceFactory
from voice.voice_service import VoiceService

async def async_input(prompt: str = "") -> str:
    """
    Read line from stdin asynchronously using a background thread executor.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)

class VoiceController:
    """
    User interaction interface that starts/stops the VoiceService.
    Decoupled from specific provider implementations.
    """
    def __init__(self):
        # Resolve dependencies using factory registry (Dependency Injection)
        self.stt = STTProviderFactory.get_provider()
        self.tts = TTSProviderFactory.get_provider()
        self.chat_service = ServiceFactory.get_chat_service()
        
        self.session = VoiceSession()
        self.voice_service = VoiceService(
            stt=self.stt,
            tts=self.tts,
            chat_service=self.chat_service,
            session=self.session
        )

    async def run(self) -> None:
        """
        Runs the interactive Push-to-Talk console loop.
        """
        if not voice_settings.VOICE_ENABLED:
            voice_logger.warning("Voice interface is disabled in config.")
            return

        voice_logger.info("Starting Voice Pipeline...")
        await self.voice_service.start()
        
        print("\n" + "="*50)
        print("  JARVIS VOICE INTERFACE - PUSH-TO-TALK MODE")
        print("="*50)
        print("Instructions:")
        print("  1. Press [Enter] to START recording.")
        print("  2. Speak clearly into your microphone.")
        print("  3. Press [Enter] again to STOP recording and get AI response.")
        print("  4. Type 'exit' and press [Enter] to quit.")
        print("="*50 + "\n")

        try:
            while True:
                user_action = await async_input("\nPress [Enter] to start speaking (or type 'exit'): ")
                if user_action.strip().lower() == "exit":
                    print("Exiting JARVIS Voice Interface...")
                    break
                
                # Start audio capture
                print("\n[Listening...] Speak now.")
                await self.voice_service.trigger_recording_start()
                
                # Wait for user input to stop recording
                await async_input("Recording... Press [Enter] to stop and process audio: ")
                
                print("\n[Processing...] Transcribing and thinking...")
                response = await self.voice_service.trigger_recording_stop()
                
                print(f"\nJARVIS: {response}")
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nShutting down controller...")
        finally:
            await self.voice_service.stop()

async def main():
    try:
        controller = VoiceController()
        await controller.run()
    except Exception as e:
        voice_logger.error(f"Voice Controller crash: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
