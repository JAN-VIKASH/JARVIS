import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional

logger = logging.getLogger("jarvis.cognitive.infrastructure")

class BackgroundJobManager:
    """
    Unified background task manager that schedules and runs coroutines asynchronously
    without blocking the request-response chat cycle.
    """
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._started = False
        self._completed_jobs = 0
        self._failed_jobs = 0
        self._status = "initialized"

    def start(self):
        if self._started:
            return
        self._started = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._status = "healthy"
        logger.info("BackgroundJobManager worker task started successfully.")

    async def stop(self):
        self._started = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._status = "unavailable"
        logger.info("BackgroundJobManager worker task stopped.")

    def enqueue_job(self, coro_fn: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs):
        """
        Schedules a non-blocking background coroutine task.
        """
        if not self._started:
            self.start()
        self._queue.put_nowait((coro_fn, args, kwargs))
        if self._queue.qsize() > 50:
            self._status = "degraded"

    async def _worker_loop(self):
        while self._started:
            try:
                coro_fn, args, kwargs = await self._queue.get()
                try:
                    await coro_fn(*args, **kwargs)
                    self._completed_jobs += 1
                except Exception as e:
                    self._failed_jobs += 1
                    logger.error(f"Error executing background job: {str(e)}", exc_info=True)
                finally:
                    self._queue.task_done()
                    if self._queue.qsize() <= 50:
                        self._status = "healthy"
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in BackgroundJobManager loop: {str(e)}", exc_info=True)
                await asyncio.sleep(1)

    def get_status(self) -> str:
        if not self._started:
            return "initialized"
        return self._status
