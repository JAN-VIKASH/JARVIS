"""
Local, offline Wake Word detection engine using openWakeWord.
"""
import os
import numpy as np
import logging

logger = logging.getLogger("jarvis.voice.wake_word")

class WakeWordDetector:
    """
    Evaluates raw 16kHz float32 audio chunks in real-time.
    Gracefully disables itself if openwakeword is not installed or ONNX model is missing.
    """
    def __init__(self, model_path: str, threshold: float = 0.5):
        self.model_path = model_path
        self.threshold = threshold
        self._model = None
        self._is_initialized = False

    def is_available(self) -> bool:
        """
        Verifies package installation and model path. Runs safely with no crashes.
        """
        try:
            import openwakeword
            if not self.model_path or not os.path.exists(self.model_path):
                return False
            return True
        except ImportError:
            return False

    def _lazy_init(self) -> None:
        """
        Lazily loads the openWakeWord ONNX model weights.
        """
        if self._is_initialized:
            return
        
        try:
            from openwakeword.model import Model
            # Load the model directly from the configured file path
            self._model = Model(wakeword_models=[self.model_path])
            self._is_initialized = True
            logger.info(f"Loaded wake word model: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to lazily load openWakeWord model session: {e}")
            self._model = None
            self._is_initialized = False

    def predict(self, audio_chunk: np.ndarray) -> float:
        """
        Feeds a 16kHz float32 chunk (usually 1280 samples / 80ms) to openwakeword.
        Returns detection probability [0.0 - 1.0].
        Returns 0.0 if dependencies or model files are missing.
        """
        if not self.is_available():
            return 0.0

        self._lazy_init()
        if not self._model:
            return 0.0

        try:
            # openwakeword predict accepts numpy array of float32
            # It expects 1280 samples per step (80ms at 16kHz)
            # Make sure chunk size is correct. If shorter, pad with zeros.
            if len(audio_chunk) < 1280:
                audio_chunk = np.pad(audio_chunk, (0, 1280 - len(audio_chunk)), 'constant')
            elif len(audio_chunk) > 1280:
                audio_chunk = audio_chunk[:1280]

            prediction = self._model.predict(audio_chunk)
            model_name = os.path.splitext(os.path.basename(self.model_path))[0]
            
            # Extract probability score for the current frame
            if prediction:
                if isinstance(prediction, dict):
                    return float(prediction.get(model_name, 0.0))
                elif isinstance(prediction, list) and len(prediction) > 0:
                    last_pred = prediction[-1]
                    if isinstance(last_pred, dict):
                        return float(last_pred.get(model_name, 0.0))
            return 0.0
        except Exception as e:
            logger.error(f"Exception during local wake-word prediction frame: {e}")
            return 0.0
