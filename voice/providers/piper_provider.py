"""
Piper Text-to-Speech provider implementation.
"""
import os
import time
import subprocess
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sounddevice as sd
import soundfile as sf
from voice.base_tts import BaseTTS
from voice.config import voice_settings
from voice.logger import voice_logger

class PiperTTS(BaseTTS):
    """
    TTS provider using Rhasspy Piper offline voice engine.
    """
    def __init__(self):
        # Validate that binaries and models exist
        try:
            self.piper_exe = self._find_piper_exe()
            voice_logger.info(f"Piper executable verified: {self.piper_exe}")
        except Exception as e:
            voice_logger.warning(
                f"Piper executable not found. TTS will fail until download is completed. Details: {e}"
            )
            self.piper_exe = None

        model_path = os.path.join(voice_settings.VOICE_MODELS_DIR, f"{voice_settings.VOICE_NAME}.onnx")
        if not os.path.exists(model_path):
            voice_logger.warning(
                f"Voice model '{voice_settings.VOICE_NAME}' not found at '{model_path}'. "
                "Please run 'python voice/download_models.py' first."
            )
            
        self.executor = ThreadPoolExecutor(max_workers=1)

    def _find_piper_exe(self) -> str:
        bin_dir = voice_settings.PIPER_BIN_DIR
        if not os.path.exists(bin_dir):
            raise FileNotFoundError(f"Piper binary directory '{bin_dir}' does not exist.")
        
        # Check direct executable
        direct = os.path.join(bin_dir, "piper.exe")
        if os.path.exists(direct):
            return direct
            
        # Walk to find piper.exe recursively
        for root, dirs, files in os.walk(bin_dir):
            if "piper.exe" in files:
                return os.path.join(root, "piper.exe")
                
        raise FileNotFoundError(f"Could not find piper.exe inside '{bin_dir}' or its subdirectories.")

    async def synthesize_and_play(self, text: str) -> None:
        """
        Synthesize text and play audio asynchronously off the main loop thread.
        """
        if not text.strip():
            return

        if not self.piper_exe:
            try:
                self.piper_exe = self._find_piper_exe()
            except Exception as e:
                voice_logger.error("Cannot play audio: Piper executable is missing. Run download_models.py.")
                return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor,
            self._synthesize_and_play_sync,
            text
        )

    def _synthesize_and_play_sync(self, text: str) -> None:
        try:
            model_path = os.path.join(voice_settings.VOICE_MODELS_DIR, f"{voice_settings.VOICE_NAME}.onnx")
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Voice model file not found at '{model_path}'")
                
            # Create a secure temporary file to write raw wave file into
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
                
            try:
                cmd = [
                    self.piper_exe,
                    "--model", model_path,
                    "--output_file", temp_wav_path
                ]
                
                voice_logger.info(f"Synthesizing text: '{text[:60]}...'")
                start_time = time.perf_counter()
                
                # Execute Piper subprocess
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = proc.communicate(input=text.encode("utf-8"))
                
                if proc.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="ignore")
                    raise RuntimeError(f"Piper process failed with code {proc.returncode}: {error_msg}")
                    
                latency = time.perf_counter() - start_time
                voice_logger.info(f"Speech synthesized successfully | Latency: {latency:.4f}s")
                
                # Load and play audio via sounddevice
                data, fs = sf.read(temp_wav_path)
                
                playback_start = time.perf_counter()
                sd.play(data, fs)
                sd.wait()  # Wait for playback completion
                
                playback_duration = time.perf_counter() - playback_start
                voice_logger.info(f"Audio playback finished | Duration: {playback_duration:.2f}s")
                
            finally:
                # Cleanup temp wav file
                if os.path.exists(temp_wav_path):
                    try:
                        os.remove(temp_wav_path)
                    except Exception:
                        pass
                        
        except Exception as e:
            voice_logger.error(f"Failed during TTS synthesis/playback: {e}", exc_info=True)
