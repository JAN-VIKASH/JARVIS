import asyncio
import logging
from typing import Set, Dict, Any

logger = logging.getLogger("jarvis.core.gui_bus")

class GUIEventBus:
    """
    Central event broker publishing voice and agent status events to connected GUI clients.
    Thread-safe and decoupled to prevent execution blocking.
    """
    _subscribers: Set[asyncio.Queue] = set()
    _lock = asyncio.Lock()

    @classmethod
    async def subscribe(cls) -> asyncio.Queue:
        """
        Register a new client queue with bounded size to prevent memory leaks.
        """
        queue = asyncio.Queue(maxsize=100)
        async with cls._lock:
            cls._subscribers.add(queue)
            logger.debug(f"New client subscribed. Active count: {len(cls._subscribers)}")
        return queue

    @classmethod
    async def unsubscribe(cls, queue: asyncio.Queue) -> None:
        """
        Remove client queue safely.
        """
        async with cls._lock:
            if queue in cls._subscribers:
                cls._subscribers.remove(queue)
                logger.debug(f"Client unsubscribed. Active count: {len(cls._subscribers)}")

    @classmethod
    def publish(cls, event_type: str, data: Dict[str, Any]) -> None:
        """
        Publish an event to all subscribers synchronously without blocking.
        Drops oldest elements if client queue is full to prevent memory leaks.
        """
        event = {"type": event_type, "data": data}
        for queue in list(cls._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full. Dropping event.")
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error publishing to subscriber queue: {e}")
