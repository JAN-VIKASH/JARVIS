"""
Application settings configuration using Pydantic Settings.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings class loaded from environment variables and .env file.
    """
    PROJECT_NAME: str = "JARVIS AI Assistant"
    API_V1_STR: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "development"  # development, staging, production
    LOG_LEVEL: str = "INFO"
    
    # LLM Settings
    LLM_PROVIDER: str = "groq"
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    MODEL_NAME: str = "llama-3.3-70b-versatile"
    REQUEST_TIMEOUT: int = 60
    
    # Database and Memory Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///database/jarvis.db"
    SQLITE_DB_PATH: str = "database/jarvis.db"
    CHROMA_DB_PATH: str = "database/chroma"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    MEMORY_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.35
    
    # Phase 4.1 Settings
    DECAY_LOW_THRESHOLD_DAYS: int = 7
    DECAY_MEDIUM_THRESHOLD_DAYS: int = 30
    DECAY_HIGH_THRESHOLD: int = 80
    RANKING_WEIGHT_SIMILARITY: float = 0.40
    RANKING_WEIGHT_IMPORTANCE: float = 0.20
    RANKING_WEIGHT_CONFIDENCE: float = 0.15
    RANKING_WEIGHT_RECENCY: float = 0.15
    RANKING_WEIGHT_FREQUENCY: float = 0.10
    REGEX_CONFIDENCE_THRESHOLD: float = 0.60
    EMBEDDING_CACHE_SIZE: int = 500
    MAX_INDEX_RETRIES: int = 5
    
    # Phase 4.2 Response Style & Cache Settings
    DEFAULT_RESPONSE_STYLE: str = "concise"
    MAX_MEMORY_RESPONSE_WORDS: int = 20
    MAX_FACT_RESPONSE_WORDS: int = 30
    MAX_GENERAL_RESPONSE_WORDS: int = 80
    MAX_EXPLANATION_RESPONSE_WORDS: int = 500
    RESPONSE_CACHE_TTL: int = 300
    PROMPT_VERSION: str = "v4.2"
    
    # Directories (relative to the run script)
    SYSTEM_PROMPT_PATH: str = "app/prompts/system_prompt.txt"
    
    # Phase 5.2 Feature Flags
    ENABLE_GRAPH: bool = True
    ENABLE_USER_PROFILE: bool = True
    ENABLE_ALIAS_RESOLUTION: bool = True
    ENABLE_GRAPH_REASONING: bool = True

    # Reconciled Phase 5 Compression Settings
    COMPRESSION_THRESHOLD: int = 40
    COMPRESSION_TARGET: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
