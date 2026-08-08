"""
Custom FastAPI middleware.
"""

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import logging

logger = logging.getLogger("jarvis")

class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request duration and assign unique request IDs.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        
        # Add correlation ID to request state so controllers can access it
        request.state.request_id = request_id
        
        # Log request receipt
        logger.debug(f"[{request_id}] Incoming request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"[{request_id}] Request failed: {e}")
            raise e
            
        process_time = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        
        logger.info(
            f"[{request_id}] Completed request: {request.method} {request.url.path} "
            f"- Status: {response.status_code} - Processed in: {process_time:.4f}s"
        )
        return response
