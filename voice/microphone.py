"""
Microphone audio recorder service.
"""
import numpy as np
import sounddevice as sd
from voice.logger import voice_logger

class AudioRecorder:
    """
    Handles audio capture from the default input device (microphone)
    using sounddevice input streams.
    """
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.stream = None
        self._buffer = []
        self._is_recording = False

    def _audio_callback(self, indata, frames, time, status):
        """
        Callback executed by sounddevice thread when new frames are available.
        """
        if status:
            voice_logger.warning(f"Audio recording warning status: {status}")
        if self._is_recording:
            self._buffer.append(indata.copy())

    def start_recording(self) -> None:
        """
        Start non-blocking recording.
        """
        self._buffer = []
        try:
            # Verify if input devices exist
            input_device = sd.default.device[0]
            if input_device is None or input_device < 0:
                # Query default device to verify
                default_in = sd.query_hostapis()[0].get('default_input_device')
                if default_in is None or default_in < 0:
                    raise RuntimeError("No input audio devices found on the system.")
            
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._audio_callback
            )
            self._is_recording = True
            self.stream.start()
            voice_logger.info("Microphone input stream started.")
        except Exception as e:
            self._is_recording = False
            self.stream = None
            voice_logger.error(f"Could not open microphone stream: {e}")
            raise RuntimeError(f"Microphone error: {str(e)}") from e

    def stop_recording(self) -> np.ndarray:
        """
        Stop recording and return raw float32 1D audio sample array.
        """
        self._is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                voice_logger.error(f"Error closing microphone stream: {e}")
            finally:
                self.stream = None
        
        voice_logger.info("Microphone input stream stopped.")
        if not self._buffer:
            return np.array([], dtype=np.float32)

        # Merge input data frames into a single flat array
        audio_data = np.concatenate(self._buffer, axis=0)
        return audio_data.flatten()

    def close(self) -> None:
        """
        Graceful cleanup.
        """
        self._is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
