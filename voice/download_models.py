"""
Utility to download Whisper models, Piper binaries, and Piper voice models.
"""
import os
import zipfile
import urllib.request
from voice.config import voice_settings
from voice.logger import voice_logger

def download_file_with_progress(url: str, dest_path: str):
    """
    Downloads a file with basic download progress updates.
    """
    voice_logger.info(f"Downloading {url} to {dest_path}...")
    
    def report_hook(block_num, block_size, total_size):
        read_so_far = block_num * block_size
        if total_size > 0:
            percent = min(100, (read_so_far * 100) // total_size)
            if percent % 10 == 0 and block_num % 100 == 0:  # Print every 10% on blocks
                voice_logger.info(f"Progress: {percent}%")
        else:
            if block_num % 1000 == 0:
                voice_logger.info(f"Downloaded: {read_so_far // (1024 * 1024)} MB")
                
    urllib.request.urlretrieve(url, dest_path, reporthook=report_hook)
    voice_logger.info(f"Downloaded successfully: {dest_path}")

def get_piper_voice_urls(voice_name: str) -> tuple[str, str]:
    """
    Dynamically maps a standard Piper voice name (e.g. en_US-lessac-medium) to Hugging Face URLs.
    """
    parts = voice_name.split("-")
    if len(parts) == 3:
        lang_country, name, quality = parts
        lang = lang_country.split("_")[0]
        onnx_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{lang_country}/{name}/{quality}/{voice_name}.onnx"
        json_url = f"{onnx_url}.json"
        return onnx_url, json_url
    else:
        # Default fallback to en_US-lessac-medium
        return (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
        )

def download_piper_binary():
    """
    Downloads and extracts Rhasspy Piper Windows executable binaries.
    """
    bin_dir = voice_settings.PIPER_BIN_DIR
    os.makedirs(bin_dir, exist_ok=True)
    
    # Check if piper.exe already exists recursively
    piper_exe = None
    for root, dirs, files in os.walk(bin_dir):
        if "piper.exe" in files:
            piper_exe = os.path.join(root, "piper.exe")
            break
            
    if piper_exe:
        voice_logger.info(f"Piper binary already present at: {piper_exe}")
        return

    zip_url = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
    zip_path = os.path.join(bin_dir, "piper_windows_amd64.zip")
    
    # Download
    download_file_with_progress(zip_url, zip_path)
    
    # Extract
    voice_logger.info("Extracting Piper zip file...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(bin_dir)
        
    voice_logger.info(f"Extracted files to: {bin_dir}")
    
    # Clean up zip file
    try:
        os.remove(zip_path)
    except Exception:
        pass

def download_piper_voice_model():
    """
    Downloads the specified voice model .onnx and .onnx.json files.
    """
    models_dir = voice_settings.VOICE_MODELS_DIR
    os.makedirs(models_dir, exist_ok=True)
    
    voice_name = voice_settings.VOICE_NAME
    onnx_dest = os.path.join(models_dir, f"{voice_name}.onnx")
    json_dest = f"{onnx_dest}.json"
    
    if os.path.exists(onnx_dest) and os.path.exists(json_dest):
        voice_logger.info(f"Piper model '{voice_name}' already downloaded at '{models_dir}'.")
        return
        
    onnx_url, json_url = get_piper_voice_urls(voice_name)
    
    # Download ONNX model file
    download_file_with_progress(onnx_url, onnx_dest)
    # Download config json file
    download_file_with_progress(json_url, json_dest)
    voice_logger.info(f"Voice model '{voice_name}' downloaded successfully.")

def download_whisper_model():
    """
    Preloads the Whisper model to download it to local huggingface cache.
    """
    # Import inside function to avoid dependency errors before installation
    from faster_whisper import WhisperModel
    
    model_size = voice_settings.STT_MODEL
    voice_logger.info(f"Downloading Whisper '{model_size}' model...")
    
    # Instantiate with local_files_only=False to force downloader execution
    WhisperModel(model_size, device="cpu", compute_type="int8", local_files_only=False)
    voice_logger.info(f"Whisper '{model_size}' model downloaded and cached successfully.")

def download_embedding_model():
    """
    Preloads the configured sentence-transformer embedding model to huggingface cache.
    """
    from sentence_transformers import SentenceTransformer
    from app.config.settings import settings
    
    model_name = settings.EMBEDDING_MODEL
    voice_logger.info(f"Downloading SentenceTransformer '{model_name}' model...")
    SentenceTransformer(model_name, local_files_only=False)
    voice_logger.info(f"SentenceTransformer '{model_name}' model downloaded and cached successfully.")

def download_wake_word_model():
    """
    Downloads the hey_jarvis ONNX model file for wake word detection.
    """
    models_dir = voice_settings.VOICE_MODELS_DIR
    os.makedirs(models_dir, exist_ok=True)
    dest_path = os.path.join(models_dir, "hey_jarvis_v0.1.onnx")
    if os.path.exists(dest_path):
        voice_logger.info(f"Wake word model hey_jarvis_v0.1.onnx already present at: {dest_path}")
        return

    url = "https://github.com/dscripka/openWakeWord/raw/main/openwakeword/resources/models/hey_jarvis_v0.1.onnx"
    download_file_with_progress(url, dest_path)
    voice_logger.info("Wake word model downloaded successfully.")

def main():
    voice_logger.info("Starting JARVIS Voice Interface models and binaries pre-downloader...")
    try:
        download_piper_binary()
        download_piper_voice_model()
        download_whisper_model()
        download_embedding_model()
        download_wake_word_model()
        voice_logger.info("All binaries and voice models downloaded successfully! Ready for use.")
    except Exception as e:
        voice_logger.error(f"Error during downloader execution: {e}", exc_info=True)

if __name__ == "__main__":
    main()
