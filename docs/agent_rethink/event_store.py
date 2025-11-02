"""
Event Store - Append-only log with pub/sub for agent events.

Handles:
- Immutable event storage
- Multiple subscribers (WebSocket, CLI, persistence)
- Bounded queue with backpressure
- Graceful shutdown
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Callable, List, Optional

from events import AgentEvent

logger = logging.getLogger(__name__)


@dataclass
class Subscriber:
    """Event subscriber with bounded queue"""

    name: str
    queue: asyncio.Queue
    filter_fn: Optional[Callable[[AgentEvent], bool]] = None
    drop_on_full: bool = True  # Drop events if queue full (for UI streaming)

    async def publish(self, event: AgentEvent) -> bool:
        """
        Publish event to subscriber.

        Returns:
            True if published, False if dropped
        """
        # Apply filter
        if self.filter_fn and not self.filter_fn(event):
            return True  # Filtered out, not dropped

        # Try to publish
        try:
            if self.drop_on_full:
                self.queue.put_nowait(event)
            else:
                await self.queue.put(event)
            return True
        except asyncio.QueueFull:
            if self.drop_on_full:
                logger.warning(
                    f"Subscriber '{self.name}' queue full, dropping event: {event.type}"
                )
                return False
            else:
                # Blocking put with timeout
                try:
                    await asyncio.wait_for(self.queue.put(event), timeout=5.0)
                    return True
                except asyncio.TimeoutError:
                    logger.error(
                        f"Subscriber '{self.name}' timeout, dropping event: {event.type}"
                    )
                    return False


class EventStore:
    """
    Append-only event store with pub/sub.

    Thread-safe for async operations.
    """

    def __init__(self, max_history: int = 10000):
        self._events: List[AgentEvent] = []
        self._subscribers: List[Subscriber] = []
        self._lock = asyncio.Lock()
        self._max_history = max_history

    async def append(self, event: AgentEvent) -> None:
        """
        Append event and notify all subscribers.

        This is the ONLY way events enter the system.
        """
        async with self._lock:
            # Store event
            self._events.append(event)

            # Trim history if needed
            if len(self._events) > self._max_history:
                self._events = self._events[-self._max_history :]

            # Notify subscribers
            tasks = [sub.publish(event) for sub in self._subscribers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log failures
            for sub, result in zip(self._subscribers, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Subscriber '{sub.name}' failed: {result}",
                        exc_info=result,
                    )

    def subscribe(
        self,
        name: str,
        queue_size: int = 1000,
        filter_fn: Optional[Callable[[AgentEvent], bool]] = None,
        drop_on_full: bool = True,
    ) -> Subscriber:
        """
        Create a new subscriber.

        Args:
            name: Subscriber identifier
            queue_size: Max queue size
            filter_fn: Optional filter function
            drop_on_full: Drop events if queue full (vs blocking)

        Returns:
            Subscriber instance
        """
        sub = Subscriber(
            name=name,
            queue=asyncio.Queue(maxsize=queue_size),
            filter_fn=filter_fn,
            drop_on_full=drop_on_full,
        )
        self._subscribers.append(sub)
        logger.info(f"Subscriber '{name}' added (queue_size={queue_size})")
        return sub

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove subscriber"""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
            logger.info(f"Subscriber '{subscriber.name}' removed")

    async def replay(
        self, subscriber: Subscriber, from_event_id: Optional[str] = None
    ) -> None:
        """
        Replay historical events to a subscriber.

        Args:
            subscriber: Subscriber to send events to
            from_event_id: Start from this event (or from beginning if None)
        """
        async with self._lock:
            start_index = 0
            if from_event_id:
                # Find starting point
                for i, ev in enumerate(self._events):
                    if ev.event_id == from_event_id:
                        start_index = i + 1
                        break

            # Replay events
            for event in self._events[start_index:]:
                await subscriber.publish(event)

    async def get_events(
        self,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentEvent]:
        """
        Query events from store.

        Args:
            session_id: Filter by session
            run_id: Filter by run
            limit: Max results

        Returns:
            Filtered events (most recent first)
        """
        async with self._lock:
            filtered = self._events

            if session_id:
                filtered = [e for e in filtered if e.session_id == session_id]

            if run_id:
                filtered = [e for e in filtered if e.run_id == run_id]

            # Return most recent first
            return list(reversed(filtered[-limit:]))

    async def stream(
        self, subscriber: Subscriber
    ) -> AsyncIterator[AgentEvent]:
        """
        Stream events from subscriber queue.

        Use this in async for loop:
            async for event in event_store.stream(sub):
                ...
        """
        try:
            while True:
                event = await subscriber.queue.get()
                yield event
        except asyncio.CancelledError:
            logger.info(f"Subscriber '{subscriber.name}' stream cancelled")
            raise

    def get_stats(self) -> dict:
        """Get store statistics"""
        return {
            "total_events": len(self._events),
            "subscribers": len(self._subscribers),
            "subscriber_details": [
                {
                    "name": sub.name,
                    "queue_size": sub.queue.qsize(),
                    "queue_max": sub.queue.maxsize,
                }
                for sub in self._subscribers
            ],
        }
