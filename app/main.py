"""
FastAPI Main Application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.config.logging import configure_logging
from app.core.middleware import RequestTimingMiddleware
from app.core.exceptions import setup_exception_handlers
from app.api.v1 import health, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks:
    # 1. Configure logging
    configure_logging()
    
    # 2. Initialize database schemas
    from app.database.migrations import init_db
    await init_db()
    
    # 3. Warm up config / prompts
    from app.config.prompts import prompt_config
    try:
        prompt_config.get_system_prompt()
    except Exception as e:
        import logging
        logging.getLogger("jarvis").warning(f"Failed to preload system prompt: {e}")
        
    # 4. Start long-term memory background decay and retry tasks
    try:
        from app.services.factory import ServiceFactory
        memory_service = ServiceFactory.get_memory_service()
        memory_service.start()
    except Exception as e:
        import logging
        logging.getLogger("jarvis").error(f"Failed to start memory service background tasks: {e}")
        
    yield
    # Shutdown tasks
    try:
        from app.services.factory import ServiceFactory
        memory_service = ServiceFactory.get_memory_service()
        await memory_service.shutdown()
    except Exception as e:
        import logging
        logging.getLogger("jarvis").error(f"Failed to shutdown memory service: {e}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="JARVIS - Advanced AI Assistant Phase 1",
    lifespan=lifespan,
)

# Exception handlers
setup_exception_handlers(app)

# Middlewares
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)

# Direct root-level fallbacks/aliases to satisfy "GET /health" and "POST /chat" exactly:
app.include_router(health.router)
app.include_router(chat.router)
