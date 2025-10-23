"""Console Session Manager

Manages telnet connections to GNS3 node consoles.
Supports multiple concurrent sessions with output buffering and diff tracking.
"""

import asyncio
import telnetlib3
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

# ANSI escape sequence pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and normalize line endings"""
    # Remove ANSI escape codes
    text = ANSI_ESCAPE.sub('', text)

    # Normalize line endings: convert \r\n and \r to \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)

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
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    buffer: str = ""
    read_position: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def is_expired(self) -> bool:
        """Check if session has expired"""
        age = (datetime.now() - self.last_activity).total_seconds()
        return age > SESSION_TIMEOUT


class ConsoleManager:
    """Manages multiple console sessions"""

    def __init__(self):
        self.sessions: Dict[str, ConsoleSession] = {}
        self._readers: Dict[str, asyncio.Task] = {}

    async def connect(self, host: str, port: int, node_name: str) -> str:
        """Connect to a console and return session ID

        Args:
            host: Console host (GNS3 server IP)
            port: Console port number
            node_name: Name of the node for logging

        Returns:
            session_id: Unique session identifier
        """
        session_id = str(uuid.uuid4())

        try:
            # Connect via telnet
            reader, writer = await telnetlib3.open_connection(
                host, port, encoding='utf-8'
            )

            session = ConsoleSession(
                session_id=session_id,
                host=host,
                port=port,
                node_name=node_name,
                reader=reader,
                writer=writer
            )

            self.sessions[session_id] = session

            # Start background task to read console output
            self._readers[session_id] = asyncio.create_task(
                self._read_console(session)
            )

            logger.info(f"Connected to {node_name} console at {host}:{port} (session: {session_id})")
            return session_id

        except Exception as e:
            logger.error(f"Failed to connect to {node_name} console: {e}")
            raise

    async def _read_console(self, session: ConsoleSession):
        """Background task to continuously read console output"""
        try:
            while session.reader and not session.reader.at_eof():
                data = await session.reader.read(4096)
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

        except Exception as e:
            logger.error(f"Error reading console for {session.node_name}: {e}")

    async def send(self, session_id: str, data: str) -> bool:
        """Send data to console

        Args:
            session_id: Session identifier
            data: Data to send (command or keystrokes)

        Returns:
            bool: Success status
        """
        session = self.sessions.get(session_id)
        if not session or not session.writer:
            logger.error(f"Session {session_id} not found or not connected")
            return False

        try:
            # Convert bare \n to \r\n for telnet compatibility
            # But don't convert if \r\n already present
            if '\r\n' not in data and '\n' in data:
                data = data.replace('\n', '\r\n')

            session.writer.write(data)
            await session.writer.drain()
            session.update_activity()
            return True
        except Exception as e:
            logger.error(f"Failed to send to console: {e}")
            return False

    def get_output(self, session_id: str) -> Optional[str]:
        """Get current console output buffer

        Args:
            session_id: Session identifier

        Returns:
            Full console buffer (ANSI codes stripped) or None if session not found
        """
        session = self.sessions.get(session_id)
        if session:
            session.update_activity()
            return strip_ansi(session.buffer)
        return None

    def get_diff(self, session_id: str) -> Optional[str]:
        """Get new console output since last read

        Args:
            session_id: Session identifier

        Returns:
            New output since last read (ANSI codes stripped), or None if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        new_data = session.buffer[session.read_position:]
        session.read_position = len(session.buffer)
        session.update_activity()
        return strip_ansi(new_data)

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

        try:
            # Cancel reader task
            if session_id in self._readers:
                self._readers[session_id].cancel()
                try:
                    await self._readers[session_id]
                except asyncio.CancelledError:
                    pass
                del self._readers[session_id]

            # Close writer
            if session.writer:
                session.writer.close()
                await session.writer.wait_closed()

            del self.sessions[session_id]
            logger.info(f"Disconnected session {session_id} for {session.node_name}")
            return True

        except Exception as e:
            logger.error(f"Error disconnecting session: {e}")
            return False

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

    def list_sessions(self) -> Dict[str, Dict[str, any]]:
        """List all active sessions

        Returns:
            Dict of session info keyed by session_id
        """
        return {
            sid: {
                "node_name": s.node_name,
                "host": s.host,
                "port": s.port,
                "created_at": s.created_at.isoformat(),
                "buffer_size": len(s.buffer)
            }
            for sid, s in self.sessions.items()
        }
