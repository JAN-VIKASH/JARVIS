# JARVIS AI Assistant - Phase 2 Setup

JARVIS is a production-quality AI Personal Assistant inspired by the digital assistant created by Tony Stark. Phase 2 extends the core foundation with a real LLM integration using the modern OpenAI Responses API and thread-safe session conversation memory tracking.

---

## Key Features

- **Asynchronous Design**: Built on modern asynchronous Python patterns using FastAPI.
- **Provider Factory Pattern**: A central `LLMProviderFactory` resolves provider subclasses (`OpenAIProvider`, `PlaceholderLLM`) depending on settings. Exposes a stable interface so routes are decoupled from provider implementations.
- **Abstract Memory Layer**: Features a base `BaseMemory` class. The default `InMemoryMemory` tracks the last 10 user-assistant exchanges (20 total messages) per session and is easily swappable with Redis/Postgres.
- **Production-Ready Client Integration**: Interfaced via Async OpenAI Responses API (`client.responses.create`) with custom exponential backoff retry loops for transient rate limits or connection drops.
- **Stability and Telemetry**: The client API contract (`ChatResponse`) remains stable while internal telemetry metrics (latency, token usage) are routed to log outputs.

---

## Directory Overview

```text
jarvis/
│
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── health.py       # API status check routes
│   │       └── chat.py         # AI conversational route with session tracking
│   │
│   ├── core/
│   │   ├── constants.py        # Global constants
│   │   ├── dependencies.py     # Injection providers (LLM, Memory, Prompt)
│   │   ├── exceptions.py       # Centralized exception mappings
│   │   └── middleware.py       # Correlation and request timing logic
│   │
│   ├── config/
│   │   ├── settings.py         # Settings loader using pydantic-settings
│   │   ├── logging.py          # Unified log setup handler
│   │   └── prompts.py          # Prompt caching mechanisms
│   │
│   ├── services/
│   │   └── llm/
│   │       ├── base.py         # BaseLLM ABC interface
│   │       ├── placeholder.py  # Mock provider implementation
│   │       ├── openai_provider.py # Real OpenAI provider using Responses API
│   │       ├── factory.py      # Provider factory module
│   │       └── __init__.py     # Factory loader entrypoint
│   │
│   ├── models/
│   │       └── chat_models.py  # Validation schemas and internal DTOs
│   │
│   ├── prompts/
│   │       └── system_prompt.txt # Prompt instructions template
│   │
│   ├── utils/
│   │   ├── logger.py           # Standard log instantiator
│   │   ├── helpers.py          # Helper functions (time metrics)
│   │   └── file_loader.py      # Async anyio file reader helpers
│   │
│   ├── __init__.py
│   └── main.py                 # FastAPI system initializer
│
├── agents/                     # Placeholder for agent setups
├── memory/                     # Memory architectures
│   ├── base.py                 # BaseMemory ABC interface
│   └── in_memory.py            # InMemoryMemory thread-safe deques
│
├── tools/                      # Placeholder for system integration tools
├── database/                   # Placeholder for database schemas
├── frontend/                   # Placeholder for web panels
├── docs/                       # Comprehensive documentation
│   ├── architecture.md         # Architecture design details
│   ├── roadmap.md              # Long-term feature progression
│   └── api.md                  # Detailed API endpoints reference
│
├── tests/                      # Testing folders
├── .env.example                # Config template
├── .gitignore                  # Git settings
├── README.md                   # Setup guide
├── requirements.txt            # Package list
└── run.py                      # Server starter script
```

---

## Installation & Running

Follow these steps to run the project locally.

### Prerequisites

- Python 3.12 or higher.

### 1. Create a Virtual Environment

Navigate to the project root and create a clean environment:

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

Install all requirements (includes `openai`):

```bash
pip install -r requirements.txt
```

### 3. Setup Configuration Settings

Configure your `.env` configuration file from the template:

```bash
copy .env.example .env
```

Open `.env` and configure:
```env
LLM_PROVIDER="openai"
OPENAI_API_KEY="your-real-openai-api-key-here"
MODEL_NAME="gpt-5.5" # Switch to gpt-4o or gpt-4o-mini if testing locally
REQUEST_TIMEOUT=60
```

### 4. Run the Server

Start the application:

```bash
python run.py
```

The server is running on `http://127.0.0.1:8000`.

---

## Verification

You can verify the API is functioning and tracking memory using cURL:

### 1. Health Endpoint (`GET /health`)

```bash
curl http://127.0.0.1:8000/health
```

### 2. Conversational Session Test (`POST /chat`)

Verify session history by naming yourself first:

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d "{\"message\": \"My name is John.\", \"session_id\": \"session_john\"}"
```

Follow up in the same session:

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d "{\"message\": \"What is my name?\", \"session_id\": \"session_john\"}"
```

Check logs to inspect internal performance logs (latency, model provider metadata, token usage parameters).

---

## Phase 3: Voice Interface

Phase 3 introduces a fully offline, local Voice Interface for JARVIS, enabling users to speak through a microphone and receive audio responses.

### Voice Architecture & Features
- **Push-to-Talk (PTT)**: Interactive speech interface triggered by keypresses. Press `Enter` to start speaking, and `Enter` again to submit.
- **Speech-to-Text (STT)**: Locally executed **Faster-Whisper** engine running on CPU.
- **Text-to-Speech (TTS)**: Locally executed **Piper TTS** engine running via the optimized standalone executable.
- **Modular & Decoupled Design**: A unified `ChatService` exposes core chat logic to both the REST route handlers and the `VoiceService` pipeline. Provider factories resolve STT and TTS engines dynamically under abstract interfaces.

### Prerequisites & Microphone
- **Audio input/output hardware**: A working microphone and speaker connected as the system default.
- On Windows, `sounddevice` automatically packages PortAudio binaries out-of-the-box.

### Setup and Downloading Models
The large model weights and standalone executables are kept separate from the application code.

1. **Pre-download Voice Models**:
   Run the preloader utility script to download the Whisper base model and the Piper binaries/voice files:
   ```bash
   python -m voice.download_models
   ```
   This will download:
   - Standalone Piper Windows binary zip (extracted to `voice/bin/piper/`).
   - `en_US-lessac-medium` ONNX voice model & json settings (saved to `voice/models/`).
   - Faster-Whisper `base` model (saved to local HuggingFace cache folder).

2. **Configuration (`.env`)**:
   Adjust configurations in your `.env` file if desired:
   ```env
   # Voice Configuration
   VOICE_ENABLED=true
   VOICE_NAME="en_US-lessac-medium"
   STT_PROVIDER="faster_whisper"
   TTS_PROVIDER="piper"
   STT_MODEL="base"
   VOICE_MODELS_DIR="voice/models"
   PIPER_BIN_DIR="voice/bin/piper"
   ```

### Running the Voice Interface
1. **Start the FastAPI Backend Server** (required for `ChatService` dependencies context):
   ```bash
   python run.py
   ```
2. **Launch the Voice Console**:
   In a separate terminal shell (with the virtual environment activated), start the interactive voice shell:
   ```bash
   python -m voice.voice_controller
   ```
   Follow the on-screen instructions: press `Enter` to record, speak, and press `Enter` again to send your voice command.
