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
        Runs the interactive console loops supporting both PTT and Wake Word modes.
        """
        if not voice_settings.VOICE_ENABLED:
            voice_logger.warning("Voice interface is disabled in config.")
            return

        print("\n" + "="*50)
        print("  JARVIS VOICE INTERFACE OPERATING MODES")
        print("="*50)
        print("  1. Continuous Wake Word Mode (\"Hey Jarvis\")")
        print("  2. Push-to-Talk (PTT) Mode [Default]")
        print("="*50 + "\n")

        mode = await async_input("Select mode option (1 or 2): ")
        if mode.strip() == "1":
            if not self.voice_service.wake_detector.is_available():
                print("\n[Warning] Wake word detection is unavailable (missing library or ONNX model file).")
                print("Falling back to standard Push-to-Talk Mode.\n")
                voice_settings.WAKE_WORD_ENABLED = False
            else:
                voice_settings.WAKE_WORD_ENABLED = True
                print("\nWake Word Mode Enabled! JARVIS will listen continuously for \"Hey Jarvis\".\n")
        else:
            voice_settings.WAKE_WORD_ENABLED = False
            print("\nPush-to-Talk Mode Enabled!\n")

        voice_logger.info("Starting Voice Pipeline...")
        await self.voice_service.start()

        try:
            if voice_settings.WAKE_WORD_ENABLED:
                print("JARVIS is listening... Type 'exit' and press [Enter] to quit.")
                while True:
                    user_input = await async_input()
                    if user_input.strip().lower() == "exit":
                        print("Exiting JARVIS Voice Interface...")
                        break
            else:
                print("Instructions:")
                print("  1. Press [Enter] to START recording.")
                print("  2. Speak clearly into your microphone.")
                print("  3. Press [Enter] again to STOP recording and get AI response.")
                print("  4. Type 'exit' and press [Enter] to quit.")
                print("="*50 + "\n")

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
