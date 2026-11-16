"""Console Session Manager

Manages telnet connections to GNS3 node consoles.
Supports multiple concurrent sessions with output buffering and diff tracking.
"""

import asyncio
import contextlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

import telnetlib3
from interfaces import IConsoleManager

logger = logging.getLogger(__name__)

# ANSI escape sequence pattern
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and normalize line endings"""
    # Remove ANSI escape codes
    text = ANSI_ESCAPE.sub("", text)

    # Normalize line endings: convert \r\n and \r to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB per session
SESSION_TIMEOUT = 1800  # 30 minutes


@dataclass
class ConsoleSession:
    """Represents an active console session"""

    session_id: str
    host: str
    port: int
    node_name: str
    node_id: str = ""  # GNS3 node UUID - used to detect stale sessions after node recreation
    # telnetlib3 TelnetReaderUnicode / TelnetWriterUnicode (encoding="utf-8")
    reader: Any = None
    writer: Any = None
    buffer: str = ""
    read_position: int = 0
    accessed_terminal: bool = False  # Track if terminal has been read at least once
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # GM-108: the telnet connection under a session can be reopened in place
    reconnects: int = 0  # times the connection was reopened
    last_error: str | None = None  # why the connection was last lost or failed to reopen
    notice: str | None = None  # one-shot message for the next tool result (pop_notice_by_node)
    reopen_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if session has expired"""
        age = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return age > SESSION_TIMEOUT


class ConsoleManager(IConsoleManager):
    """Manages multiple console sessions

    Thread-safe management of telnet console connections with automatic
    output buffering and session tracking.
    """

    def __init__(self):
        self.sessions: Dict[str, ConsoleSession] = {}  # session_id → ConsoleSession
        self._readers: Dict[str, asyncio.Task] = {}  # session_id → reader task
        self._node_sessions: Dict[str, str] = {}  # node_name → session_id
        self._lock = asyncio.Lock()  # Protect shared state from race conditions

    async def connect(self, host: str, port: int, node_name: str, node_id: str = "") -> str:
        """Connect to a console and return session ID

        Thread-safe. If already connected to this node, returns existing session ID.
        Detects stale sessions when node_id changes (node deleted and recreated with same name).

        Args:
            host: Console host (GNS3 server IP)
            port: Console port number
            node_name: Name of the node for logging
            node_id: GNS3 node UUID - used to detect stale sessions after node recreation

        Returns:
            session_id: Unique session identifier

        A session whose telnet connection was closed, or whose console port changed,
        is reopened in place (GM-108): same session_id, buffer and read-first state.
        Raises the connection error when the reopen fails.
        """
        stale_id = None
        reopen_session = None
        async with self._lock:
            existing_id = self._node_sessions.get(node_name)
            existing_session = self.sessions.get(existing_id) if existing_id else None
            if existing_session:
                # Detect stale session: node_id changed means node was recreated
                if node_id and existing_session.node_id and node_id != existing_session.node_id:
                    logger.warning(
                        f"Stale session detected for {node_name}: "
                        f"cached node_id={existing_session.node_id}, "
                        f"current node_id={node_id}. Reconnecting."
                    )
                    # Disconnect stale session (release lock first to avoid deadlock)
                    stale_id = existing_id
                else:
                    if node_id and not existing_session.node_id:
                        existing_session.node_id = node_id
                    if (
                        existing_session.host == host
                        and existing_session.port == port
                        and self._is_alive(existing_session)
                    ):
                        logger.debug(f"Reusing existing session for {node_name}: {existing_id}")
                        return existing_session.session_id
                    reopen_session = existing_session

            session_id = str(uuid.uuid4())

        if reopen_session:
            await self._reopen(reopen_session, host, port)
            return reopen_session.session_id

        # Disconnect stale session outside lock
        if stale_id:
            await self.disconnect(stale_id)

        try:
            # Connect via telnet (outside lock - network I/O)
            reader, writer = await telnetlib3.open_connection(host, port, encoding="utf-8")

            session = ConsoleSession(
                session_id=session_id,
                host=host,
                port=port,
                node_name=node_name,
                node_id=node_id,
                reader=reader,
                writer=writer,
            )

            async with self._lock:
                # Double-check node_name mapping (another connection might have completed)
                if node_name in self._node_sessions:
                    existing_id = self._node_sessions[node_name]
                    if existing_id in self.sessions:
                        # Another connection won the race - close this one and return existing
                        writer.close()
                        await writer.wait_closed()
                        logger.debug(
                            f"Race condition detected for {node_name}, using existing session"
                        )
                        return existing_id

                # Store session
                self.sessions[session_id] = session
                self._node_sessions[node_name] = session_id

            # Start background task to read console output (outside lock)
            self._readers[session_id] = asyncio.create_task(self._read_console(session, reader))

            logger.info(
                f"Connected to {node_name} console at {host}:{port} (session: {session_id})"
            )
            return session_id

        except Exception as e:
            logger.error(f"Failed to connect to {node_name} console: {e}")
            raise

    async def _read_console(self, session: ConsoleSession, reader=None):
        """Background task to continuously read console output

        Reads only its own connection (``reader``), so a task left over from before
        a reopen never reads the new connection.
        """
        reader = reader if reader is not None else session.reader
        try:
            while reader is not None and not reader.at_eof():
                data = await reader.read(4096)
                if data:
                    session.buffer += data
                    session.update_activity()

                    # Trim buffer if it exceeds max size
                    if len(session.buffer) > MAX_BUFFER_SIZE:
                        trim_size = MAX_BUFFER_SIZE // 2
                        session.buffer = session.buffer[-trim_size:]
                        # Adjust read position
                        if session.read_position > trim_size:
                            session.read_position = 0

                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

            session.last_error = "closed by the remote end"
            logger.warning(f"Console connection of {session.node_name} closed by the remote end")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            session.last_error = f"read failed: {e}"
            logger.error(f"Error reading console for {session.node_name}: {e}")

    def _is_alive(self, session: ConsoleSession) -> bool:
        """True while the session's telnet connection can still carry data.

        telnetlib3 drops a write to a closed connection without an error and its
        drain() raises only when the connection was reset (GM-108), so the state
        has to be checked before sending, not inferred from the send.
        """
        reader, writer = session.reader, session.writer
        if reader is None or writer is None:
            return False
        try:
            if writer.is_closing():
                return False
            if reader.at_eof() or reader.exception() is not None:
                return False
        except Exception:
            return False
        task = self._readers.get(session.session_id)
        return not (task is not None and task.done())

    def _dead_reason(self, session: ConsoleSession) -> str:
        """Short description of why a session's connection is not usable"""
        if session.last_error:
            return session.last_error
        if session.reader is None or session.writer is None:
            return "not connected"
        return "connection closed"

    async def _reopen(
        self, session: ConsoleSession, host: str | None = None, port: int | None = None
    ) -> None:
        """Replace the session's telnet connection, keeping id, buffer and read-first state

        Raises the connection error when the console cannot be reached.
        """
        host = host or session.host
        port = port or session.port
        async with session.reopen_lock:
            # Another operation may have reopened it while this one waited
            if session.host == host and session.port == port and self._is_alive(session):
                return

            reason = self._dead_reason(session)
            if session.host != host or session.port != port:
                reason = f"console moved from {session.host}:{session.port} to {host}:{port}"

            old_task = self._readers.pop(session.session_id, None)
            if old_task is not None:
                old_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await old_task
            if session.writer is not None:
                with contextlib.suppress(Exception):
                    session.writer.close()
            session.reader = None
            session.writer = None

            try:
                reader, writer = await telnetlib3.open_connection(host, port, encoding="utf-8")
            except Exception as e:
                session.last_error = f"{reason}; reopening {host}:{port} failed: {e}"
                session.notice = (
                    f"Console connection is closed ({reason}) and reopening it failed: {e}"
                )
                logger.error(f"Could not reopen console of {session.node_name}: {e}")
                raise

            if self.sessions.get(session.session_id) is not session:
                # Disconnected while the reopen was in progress
                writer.close()
                raise ConnectionError(f"Console session of {session.node_name} was closed")

            session.host, session.port = host, port
            session.reader, session.writer = reader, writer
            session.reconnects += 1
            session.last_error = None
            session.notice = (
                f"Console connection was lost ({reason}) and has been reopened; "
                "output the device sent while it was closed may be missing"
            )
            self._readers[session.session_id] = asyncio.create_task(
                self._read_console(session, reader)
            )
            logger.warning(
                f"Reopened console of {session.node_name} at {host}:{port} "
                f"({reason}; reconnect #{session.reconnects})"
            )

    async def send(self, session_id: str, data: str) -> bool:
        """Send data to console

        A closed connection is reopened once, before the write or after a failed
        write, and the data sent again (GM-108). Read-first state is kept.

        Args:
            session_id: Session identifier
            data: Data to send (command or keystrokes)

        Returns:
            bool: Success status
        """
        session = self.sessions.get(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        reopened = False
        if not self._is_alive(session):
            try:
                await self._reopen(session)
            except Exception:
                return False
            reopened = True

        try:
            await self._write(session, data)
            return True
        except Exception as e:
            session.last_error = f"send failed: {e}"
            logger.error(f"Failed to send to console of {session.node_name}: {e}")
            if reopened:
                return False

        # The write raised, so the data did not go out: reopen once and resend
        try:
            await self._reopen(session)
            await self._write(session, data)
            return True
        except Exception as e:
            session.last_error = f"send after reopen failed: {e}"
            logger.error(f"Failed to send to console of {session.node_name} after reopen: {e}")
            return False

    async def _write(self, session: ConsoleSession, data: str) -> None:
        """Write and drain; raises when the connection is not usable"""
        writer = session.writer
        if writer is None or not self._is_alive(session):
            raise ConnectionError(self._dead_reason(session))
        # Send data as-is - telnetlib3 handles line endings
        writer.write(data)
        await writer.drain()
        session.update_activity()

    def get_output(self, session_id: str) -> str | None:
        """Get current console output buffer

        Args:
            session_id: Session identifier

        Returns:
            Full console buffer (ANSI codes stripped) or None if session not found
        """
        session = self.sessions.get(session_id)
        if session:
            session.update_activity()
            session.accessed_terminal = True  # Mark terminal as accessed
            return strip_ansi(session.buffer)
        return None

    def get_diff(self, session_id: str) -> str | None:
        """Get new console output since last read

        Args:
            session_id: Session identifier

        Returns:
            New output since last read (ANSI codes stripped), or None if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        new_data = session.buffer[session.read_position :]
        session.read_position = len(session.buffer)
        session.update_activity()
        session.accessed_terminal = True  # Mark terminal as accessed
        return strip_ansi(new_data)

    def has_accessed_terminal(self, session_id: str) -> bool:
        """Check if terminal has been accessed (read) at least once

        Args:
            session_id: Session identifier

        Returns:
            True if terminal has been read, False otherwise or if session not found
        """
        session = self.sessions.get(session_id)
        return session.accessed_terminal if session else False

    def has_accessed_terminal_by_node(self, node_name: str) -> bool:
        """Check if terminal has been accessed (read) at least once by node name

        Args:
            node_name: Name of the node

        Returns:
            True if terminal has been read, False otherwise or if session not found
        """
        session_id = self._node_sessions.get(node_name)
        if not session_id:
            return False
        return self.has_accessed_terminal(session_id)

    async def disconnect(self, session_id: str) -> bool:
        """Disconnect console session

        Args:
            session_id: Session identifier

        Returns:
            bool: Success status
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        # Forget the session first: a close that fails must not leave a dead
        # session behind for the next operation to reuse.
        del self.sessions[session_id]
        if self._node_sessions.get(session.node_name) == session_id:
            del self._node_sessions[session.node_name]

        reader_task = self._readers.pop(session_id, None)
        if reader_task is not None:
            reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await reader_task

        if session.writer:
            try:
                session.writer.close()
                await session.writer.wait_closed()
            except Exception as e:
                logger.warning(f"Error closing console of {session.node_name}: {e}")

        logger.info(f"Disconnected session {session_id} for {session.node_name}")
        return True

    async def cleanup_expired(self):
        """Remove expired sessions"""
        expired = [sid for sid, s in self.sessions.items() if s.is_expired()]
        for session_id in expired:
            await self.disconnect(session_id)
            logger.info(f"Cleaned up expired session {session_id}")

    async def close_all(self):
        """Close all console sessions"""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.disconnect(session_id)

    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active sessions

        Returns:
            Dict of session info keyed by session_id
        """
        return {
            sid: {
                "node_name": s.node_name,
                "connected": self._is_alive(s),
                "host": s.host,
                "port": s.port,
                "created_at": s.created_at.isoformat(),
                "buffer_size": len(s.buffer),
                "reconnects": s.reconnects,
                "last_error": s.last_error,
            }
            for sid, s in self.sessions.items()
        }

    def is_connected(self, session_id: str) -> bool:
        """True if the session exists and its telnet connection is open"""
        session = self.sessions.get(session_id)
        return session is not None and self._is_alive(session)

    def pop_notice_by_node(self, node_name: str) -> str | None:
        """Return and clear the session's pending notice (connection reopened or lost)"""
        session_id = self._node_sessions.get(node_name)
        session = self.sessions.get(session_id) if session_id else None
        if not session or not session.notice:
            return None
        notice, session.notice = session.notice, None
        return notice

    def last_error_by_node(self, node_name: str) -> str | None:
        """Why the node's console connection was last lost or failed to reopen"""
        session_id = self._node_sessions.get(node_name)
        session = self.sessions.get(session_id) if session_id else None
        return session.last_error if session else None

    # Node-name based convenience methods

    def get_session_id(self, node_name: str) -> str | None:
        """Get session ID for a node

        Args:
            node_name: Node name

        Returns:
            session_id or None if not found
        """
        return self._node_sessions.get(node_name)

    def has_session(self, node_name: str) -> bool:
        """Check if a session exists for a node

        Args:
            node_name: Node name

        Returns:
            True if session exists and is active
        """
        session_id = self._node_sessions.get(node_name)
        if not session_id:
            return False
        return session_id in self.sessions

    async def send_by_node(self, node_name: str, data: str) -> bool:
        """Send data to console by node name

        Args:
            node_name: Node name
            data: Data to send

        Returns:
            Success status
        """
        session_id = self.get_session_id(node_name)
        if not session_id:
            return False
        return await self.send(session_id, data)

    def get_output_by_node(self, node_name: str) -> str | None:
        """Get console output by node name

        Args:
            node_name: Node name

        Returns:
            Console buffer or None
        """
        session_id = self.get_session_id(node_name)
        if not session_id:
            return None
        return self.get_output(session_id)

    def get_diff_by_node(self, node_name: str) -> str | None:
        """Get new console output by node name

        Args:
            node_name: Node name

        Returns:
            New output since last read or None
        """
        session_id = self.get_session_id(node_name)
        if not session_id:
            return None
        return self.get_diff(session_id)

    async def disconnect_by_node(self, node_name: str) -> bool:
        """Disconnect console by node name

        Args:
            node_name: Node name

        Returns:
            Success status
        """
        session_id = self.get_session_id(node_name)
        if not session_id:
            return False
        return await self.disconnect(session_id)
