"""GNS3 Notification Manager

Subscribes to GNS3 v3 notification streams and buffers events for on-demand reading.
Mirrors the ConsoleManager pattern: background task reads stream, buffer stores events.

v0.54.0: Initial implementation
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# Maximum number of events to buffer before trimming oldest
MAX_BUFFER_SIZE = 5000
TRIM_TO_SIZE = 3000


class NotificationManager:
    """Manages GNS3 notification stream subscriptions and event buffering.

    Supports both controller-level (/v3/notifications) and
    project-level (/v3/projects/{id}/notifications) streams.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []
        self._read_index: int = 0  # Index up to which events have been read (for diff mode)
        self._task: asyncio.Task | None = None
        self._scope: str | None = None  # "controller" or project_id
        self._connected: bool = False
        self._error: str | None = None
        self._subscribe_time: datetime | None = None
        self._event_count: int = 0  # Total events received (including trimmed)

    @property
    def is_subscribed(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def scope(self) -> str | None:
        return self._scope

    async def subscribe(
        self,
        base_url: str,
        token: str,
        project_id: str | None = None,
        verify_ssl: bool = True,
    ) -> str:
        """Subscribe to GNS3 notification stream.

        Args:
            base_url: GNS3 server base URL (e.g., http://192.168.1.20:80)
            token: JWT authentication token
            project_id: If provided, subscribe to project notifications; otherwise controller-level
            verify_ssl: Whether to verify SSL certificates

        Returns:
            Status message
        """
        if self.is_subscribed:
            return (
                f"Already subscribed to notifications "
                f"(scope: {self._scope}, events buffered: {len(self._events)})"
            )

        # Clear previous state
        self._events.clear()
        self._read_index = 0
        self._error = None
        self._event_count = 0

        if project_id:
            url = f"{base_url}/v3/projects/{project_id}/notifications"
            self._scope = project_id
        else:
            url = f"{base_url}/v3/notifications"
            self._scope = "controller"

        self._subscribe_time = datetime.now()
        self._task = asyncio.create_task(
            self._stream_reader(url, token, verify_ssl),
            name=f"notifications-{self._scope}",
        )

        # Wait briefly for connection to establish
        await asyncio.sleep(0.5)

        if self._error:
            return f"Subscription failed: {self._error}"

        scope_desc = f"project {project_id}" if project_id else "controller (all events)"
        return f"Subscribed to {scope_desc} notifications"

    async def unsubscribe(self) -> str:
        """Stop listening to notifications and clear buffer."""
        if not self.is_subscribed:
            return "Not currently subscribed"

        scope = self._scope
        event_count = self._event_count

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

        self._task = None
        self._scope = None
        self._connected = False
        self._events.clear()
        self._read_index = 0

        return f"Unsubscribed from {scope} notifications ({event_count} total events received)"

    def read(
        self,
        mode: str = "diff",
        filter_action: str | None = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Read buffered notification events.

        Args:
            mode: Reading mode
                - "diff": New events since last read (default, most efficient)
                - "all": All buffered events
                - "last": Last N events (uses limit parameter)
            filter_action: Filter by event action (e.g., "node.updated", "log.error")
            limit: Max events to return (default: 100)

        Returns:
            Dict with status, events, and metadata
        """
        result: Dict[str, Any] = {
            "subscribed": self.is_subscribed,
            "scope": self._scope,
            "connected": self._connected,
            "total_buffered": len(self._events),
            "total_received": self._event_count,
        }

        if self._error:
            result["error"] = self._error

        if not self._events:
            result["events"] = []
            result["count"] = 0
            return result

        # Select events based on mode
        if mode == "diff":
            events = self._events[self._read_index :]
            self._read_index = len(self._events)
        elif mode == "last":
            events = self._events[-limit:]
        else:  # "all"
            events = self._events[:]

        # Apply action filter
        if filter_action:
            events = [e for e in events if e.get("action", "").startswith(filter_action)]

        # Apply limit
        if len(events) > limit:
            events = events[-limit:]

        result["events"] = events
        result["count"] = len(events)
        result["mode"] = mode

        return result

    def status(self) -> Dict[str, Any]:
        """Get subscription status."""
        return {
            "subscribed": self.is_subscribed,
            "scope": self._scope,
            "connected": self._connected,
            "error": self._error,
            "buffered_events": len(self._events),
            "total_received": self._event_count,
            "unread_events": len(self._events) - self._read_index,
            "subscribe_time": (
                self._subscribe_time.strftime("%H:%M:%S %d.%m.%Y") if self._subscribe_time else None
            ),
        }

    async def _stream_reader(self, url: str, token: str, verify_ssl: bool) -> None:
        """Background task that reads the notification stream.

        GNS3 sends line-delimited JSON over a long-lived HTTP connection.
        Each line is a complete JSON object with 'action' and 'event' fields.
        """
        headers = {"Authorization": f"Bearer {token}"}
        reconnect_delay = 5

        while True:
            try:
                async with (
                    httpx.AsyncClient(verify=verify_ssl) as client,
                    client.stream("GET", url, headers=headers, timeout=None) as response,
                ):
                    response.raise_for_status()
                    self._connected = True
                    self._error = None
                    reconnect_delay = 5  # Reset on successful connect
                    logger.info(f"Connected to notification stream: {url}")

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning(f"Skipping non-JSON line: {line[:100]}")
                            continue

                        # Add receive timestamp
                        event["_received_at"] = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
                        self._events.append(event)
                        self._event_count += 1

                        # Trim buffer if too large
                        if len(self._events) > MAX_BUFFER_SIZE:
                            self._events = self._events[-TRIM_TO_SIZE:]
                            # Adjust read index
                            trimmed = MAX_BUFFER_SIZE - TRIM_TO_SIZE + 1
                            self._read_index = max(0, self._read_index - trimmed)
                            logger.debug(f"Trimmed notification buffer to {TRIM_TO_SIZE} events")

            except asyncio.CancelledError:
                logger.info("Notification stream reader cancelled")
                self._connected = False
                return

            except httpx.HTTPStatusError as e:
                self._connected = False
                self._error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                logger.error(f"Notification stream HTTP error: {self._error}")
                # Don't reconnect on auth errors
                if e.response.status_code in (401, 403):
                    return

            except Exception as e:
                self._connected = False
                self._error = str(e)
                logger.warning(f"Notification stream disconnected: {e}")

            # Reconnect with backoff (up to 60s)
            logger.info(f"Reconnecting to notification stream in {reconnect_delay}s...")
            try:
                await asyncio.sleep(reconnect_delay)
            except asyncio.CancelledError:
                return
            reconnect_delay = min(reconnect_delay * 2, 60)

    async def close(self) -> None:
        """Clean shutdown - cancel stream task."""
        if self.is_subscribed:
            await self.unsubscribe()
