"""
SSH Session Manager with Dual Storage

Manages Netmiko SSH connections with two storage systems:
1. Continuous buffer - Real-time stream of all output (like console)
2. Command history - Per-command jobs with individual outputs and metadata

Handles connection lifecycle, error detection, and adaptive async execution.
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
    SSHException
)

from .models import (
    Job,
    JobSummary,
    SSHDeviceConfig,
    SSHConnectionError,
    SessionInfo
)

logger = logging.getLogger(__name__)


# ============================================================================
# SSH Error Detection and Mapping
# ============================================================================

def classify_ssh_error(exception: Exception) -> SSHConnectionError:
    """
    Classify SSH connection errors and provide helpful suggestions

    Emphasizes using console tools to configure SSH access first.
    """
    error_str = str(exception)

    # Authentication failures
    if isinstance(exception, NetmikoAuthenticationException):
        return SSHConnectionError(
            error_type="authentication_failed",
            error="SSH authentication failed",
            details=error_str,
            suggestion=(
                "Wrong username or password. "
                "Use console tools to configure SSH access first:\n"
                "1. send_console('NodeName', 'configure terminal\\n')\n"
                "2. send_console('NodeName', 'username admin privilege 15 secret YourPassword\\n')\n"
                "3. send_console('NodeName', 'crypto key generate rsa modulus 2048\\n')\n"
                "4. send_console('NodeName', 'ip ssh version 2\\n')\n"
                "Then retry SSH connection."
            )
        )

    # Connection refused (SSH not enabled)
    if "Connection refused" in error_str or "Errno 10061" in error_str:
        return SSHConnectionError(
            error_type="connection_refused",
            error="SSH connection refused",
            details=error_str,
            suggestion=(
                "SSH server not running on device. "
                "Use console tools to enable SSH:\n"
                "1. send_console('NodeName', 'configure terminal\\n')\n"
                "2. send_console('NodeName', 'crypto key generate rsa modulus 2048\\n')\n"
                "3. send_console('NodeName', 'ip ssh version 2\\n')\n"
                "4. send_console('NodeName', 'line vty 0 4\\n')\n"
                "5. send_console('NodeName', 'transport input ssh\\n')\n"
                "Then retry SSH connection."
            )
        )

    # Timeout errors
    if isinstance(exception, NetmikoTimeoutException):
        return SSHConnectionError(
            error_type="timeout",
            error="SSH connection timeout",
            details=error_str,
            suggestion=(
                "Connection timed out. Possible causes:\n"
                "1. Wrong IP address - verify with: list_nodes()\n"
                "2. Network unreachable - check GNS3 lab is running\n"
                "3. Firewall blocking port 22\n"
                "4. Device is booting - wait and retry"
            )
        )

    # Host unreachable
    if "No route to host" in error_str or "Host unreachable" in error_str:
        return SSHConnectionError(
            error_type="host_unreachable",
            error="Host unreachable",
            details=error_str,
            suggestion=(
                "Network unreachable. Check:\n"
                "1. GNS3 project is open: open_project('ProjectName')\n"
                "2. Node is started: set_node('NodeName', action='start')\n"
                "3. IP address is correct: list_nodes() to verify\n"
                "4. Network connectivity from GNS3 host"
            )
        )

    # Unknown error
    return SSHConnectionError(
        error_type="unknown",
        error="SSH connection failed",
        details=error_str,
        suggestion=(
            "Unexpected error. Check:\n"
            "1. Device type is correct (cisco_ios, juniper, arista_eos, etc.)\n"
            "2. SSH is configured on device (use console tools)\n"
            "3. GNS3 lab is running and node is started\n"
            "See error details above for more information."
        )
    )


# ============================================================================
# SSH Session Manager
# ============================================================================

class SSHSessionManager:
    """
    Manages SSH sessions with dual storage architecture

    Storage System 1: Continuous Buffer
    - All command outputs combined in chronological order
    - 10MB max, trim to 5MB when exceeded
    - Supports diff mode (track read position)

    Storage System 2: Command History
    - Every command creates a Job record (even synchronous)
    - Jobs persist until session cleanup
    - Searchable by command text
    - Ordered by sequence_number

    Session Management (v0.1.6):
    - 30-minute TTL with automatic expiry detection
    - Activity tracking - updates on every operation
    - Health checks - detects stale/closed connections
    - Auto-cleanup on socket errors
    """

    MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB
    TRIM_BUFFER_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_HISTORY_JOBS = 1000  # Per session
    SESSION_TTL = 30 * 60  # 30 minutes in seconds (v0.1.6)

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.connections: Dict[str, ConnectHandler] = {}  # Netmiko connections

    # ========================================================================
    # Session Lifecycle
    # ========================================================================

    async def create_session(
        self,
        node_name: str,
        device_config: SSHDeviceConfig,
        persist: bool,
        force_recreate: bool
    ) -> Tuple[str, Optional[SSHConnectionError]]:
        """
        Create or recreate SSH session

        Returns:
            (session_id, error) - error is None if successful
        """
        # Check existing session (v0.1.6: health check + TTL)
        if node_name in self.sessions:
            if force_recreate:
                logger.info(f"Force recreate requested for {node_name}")
                await self.disconnect_session(node_name)
            else:
                # Check if session is expired (30min TTL)
                if self._is_session_expired(node_name):
                    logger.info(f"Session expired for {node_name}, recreating")
                    await self.disconnect_session(node_name)
                # Check if connection is still alive (health check)
                elif not await self._is_session_healthy(node_name):
                    logger.warning(f"Session unhealthy for {node_name}, recreating")
                    await self.disconnect_session(node_name)
                else:
                    # Session healthy and not expired - reuse it
                    session = self.sessions[node_name]
                    # Update activity on reuse
                    self._update_activity(node_name)
                    logger.info(f"Session already exists for {node_name}, returning existing (healthy)")
                    return session.session_id, None

        # Create Netmiko connection
        try:
            logger.info(f"Connecting to {node_name} ({device_config.host})")

            # Convert to Netmiko dict
            netmiko_params = device_config.model_dump()

            # Use asyncio to run blocking Netmiko connection in thread
            connection = await asyncio.to_thread(
                ConnectHandler,
                **netmiko_params
            )

            logger.info(f"SSH connection established: {node_name}")

        except (NetmikoAuthenticationException, NetmikoTimeoutException, SSHException) as e:
            logger.error(f"SSH connection failed for {node_name}: {e}")
            error = classify_ssh_error(e)
            return "", error

        except Exception as e:
            logger.error(f"Unexpected error connecting to {node_name}: {e}")
            error = classify_ssh_error(e)
            return "", error

        # Create session
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        session = SessionInfo(
            session_id=session_id,
            node_name=node_name,
            device_config=device_config,
            persist=persist,
            created_at=now,
            last_activity=now,  # Initialize activity timestamp (v0.1.6)
            buffer="",
            buffer_read_pos=0,
            jobs=[],
            sequence_counter=0
        )

        self.sessions[node_name] = session
        self.connections[node_name] = connection

        logger.info(f"Session created: {node_name} ({session_id})")
        return session_id, None

    async def disconnect_session(self, node_name: str) -> bool:
        """Disconnect and cleanup session"""
        if node_name not in self.sessions:
            return False

        # Close Netmiko connection
        if node_name in self.connections:
            connection = self.connections[node_name]
            await asyncio.to_thread(connection.disconnect)
            del self.connections[node_name]
            logger.info(f"SSH connection closed: {node_name}")

        # Remove session
        del self.sessions[node_name]
        logger.info(f"Session removed: {node_name}")
        return True

    def has_session(self, node_name: str) -> bool:
        """Check if session exists"""
        return node_name in self.sessions

    def get_session_info(self, node_name: str) -> Optional[SessionInfo]:
        """Get session info (or None)"""
        return self.sessions.get(node_name)

    # ========================================================================
    # Session Health and Activity Tracking (v0.1.6)
    # ========================================================================

    def _update_activity(self, node_name: str) -> None:
        """Update last_activity timestamp for session (30min TTL)"""
        if node_name in self.sessions:
            self.sessions[node_name].last_activity = datetime.now(timezone.utc)

    def _is_session_expired(self, node_name: str) -> bool:
        """Check if session has exceeded 30-minute TTL"""
        if node_name not in self.sessions:
            return True

        session = self.sessions[node_name]
        age = (datetime.now(timezone.utc) - session.last_activity).total_seconds()
        return age > self.SESSION_TTL

    async def _is_session_healthy(self, node_name: str) -> bool:
        """
        Check if SSH session is still alive

        Uses lightweight test to verify connection without full command execution.
        Returns False if socket closed or connection dead.

        Approach:
        1. Try Netmiko is_alive() method if available (Netmiko 4.0+)
        2. Fallback: Send empty command with short timeout (lightweight test)

        Returns:
            True if connection is healthy, False if dead/closed
        """
        if node_name not in self.connections:
            return False

        connection = self.connections[node_name]

        try:
            # Method 1: Try Netmiko is_alive() if available (Netmiko 4.0+)
            if hasattr(connection, 'is_alive'):
                is_alive = await asyncio.to_thread(connection.is_alive)
                if not is_alive:
                    logger.warning(f"Health check failed for {node_name}: is_alive() returned False")
                return is_alive

            # Method 2: Fallback - send empty command (very lightweight)
            # This will fail quickly if socket is closed
            await asyncio.to_thread(
                connection.send_command,
                "",
                expect_string=r".*",
                read_timeout=2
            )
            return True

        except Exception as e:
            # Any exception = connection dead
            logger.warning(f"Health check failed for {node_name}: {e}")
            return False

    # ========================================================================
    # Command Execution (Adaptive Async)
    # ========================================================================

    async def send_command_adaptive(
        self,
        node_name: str,
        command: str,
        wait_timeout: int,
        **netmiko_kwargs
    ) -> Dict:
        """
        Execute command with adaptive async pattern

        Creates Job immediately, polls for wait_timeout seconds.
        Returns output if completes, else returns job_id for polling.
        """
        if node_name not in self.sessions:
            raise ValueError(f"No session for {node_name}")

        session = self.sessions[node_name]
        connection = self.connections[node_name]

        # Update activity timestamp (v0.1.6)
        self._update_activity(node_name)

        # Create Job immediately (status=running)
        job = Job(
            job_id=str(uuid.uuid4()),
            node_name=node_name,
            command=command,
            output="",
            status="running",
            error=None,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            execution_time=None,
            sequence_number=session.sequence_counter
        )

        # Add to history
        session.jobs.append(job)
        session.sequence_counter += 1

        # Trim history if needed
        if len(session.jobs) > self.MAX_HISTORY_JOBS:
            session.jobs = session.jobs[-self.MAX_HISTORY_JOBS:]
            logger.info(f"Trimmed job history for {node_name}")

        # Start command in background
        task = asyncio.create_task(
            self._execute_netmiko_command(node_name, job.job_id, command, netmiko_kwargs)
        )

        # Poll for wait_timeout seconds
        for i in range(wait_timeout):
            await asyncio.sleep(1)
            if task.done():
                # Command completed - get result and recalculate timing
                try:
                    output = task.result()
                    # Job object updated by background task - recalculate execution time
                    if job.completed_at and job.started_at:
                        job.execution_time = (job.completed_at - job.started_at).total_seconds()

                    return {
                        "completed": True,
                        "job_id": job.job_id,
                        "output": output,
                        "execution_time": job.execution_time,
                        "started_at": job.started_at,
                        "completed_at": job.completed_at
                    }
                except Exception as e:
                    # Command failed or timed out
                    error_msg = str(e)
                    logger.error(f"Command failed: {error_msg}")

                    # Detect error type and provide helpful message (v0.1.6)
                    if "Socket is closed" in error_msg:
                        error_code = "SSH_DISCONNECTED"
                        suggested_action = (
                            "Session was stale and has been removed. "
                            "Reconnect with ssh_configure() and try again."
                        )
                    elif "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                        error_code = "TIMEOUT"
                        suggested_action = "Command timed out. Increase read_timeout or check device responsiveness."
                    else:
                        error_code = "COMMAND_FAILED"
                        suggested_action = "Check command syntax and device state."

                    # Calculate execution time for failed command
                    completed_at = datetime.now(timezone.utc)
                    exec_time = (completed_at - job.started_at).total_seconds()

                    return {
                        "completed": False,  # Mark as failed
                        "job_id": job.job_id,
                        "output": job.output if job.output else "",  # Include any partial output
                        "execution_time": exec_time,
                        "started_at": job.started_at,
                        "completed_at": completed_at,
                        "error": error_msg,
                        "error_code": error_code,
                        "suggested_action": suggested_action
                    }

        # Still running - return job_id for polling
        return {
            "completed": False,
            "job_id": job.job_id,
            "message": f"Command running. Poll GET /ssh/job/{job.job_id} for status.",
            "started_at": job.started_at
        }

    async def _execute_netmiko_command(
        self,
        node_name: str,
        job_id: str,
        command: str,
        netmiko_kwargs: Dict
    ) -> str:
        """Execute Netmiko command and update job"""
        session = self.sessions[node_name]
        connection = self.connections[node_name]

        # Find job
        job = next((j for j in session.jobs if j.job_id == job_id), None)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            # Ensure proper defaults for Netmiko send_command
            # Add delay_factor for more reliable output capture on slow devices
            if 'delay_factor' not in netmiko_kwargs:
                netmiko_kwargs['delay_factor'] = 4  # Increased for Alpine/doas commands

            # Execute command (blocking, run in thread)
            output = await asyncio.to_thread(
                connection.send_command,
                command,
                **netmiko_kwargs
            )

            # Log output size for debugging
            logger.info(f"Command output size: {len(output)} bytes")

            # Update job
            job.output = output
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.execution_time = (job.completed_at - job.started_at).total_seconds()

            # Append to buffer
            await self._append_to_buffer(node_name, output)

            logger.info(f"Command completed: {node_name} - {command[:50]}... ({job.execution_time:.2f}s)")
            return output

        except Exception as e:
            error_str = str(e)

            # Detect socket closure and cleanup stale session (v0.1.6)
            if "Socket is closed" in error_str or "Socket error" in error_str:
                logger.error(f"Stale session detected for {node_name}, cleaning up")

                # Mark job as failed
                job.status = "failed"
                job.error = "SSH connection closed - session was stale"
                job.completed_at = datetime.now(timezone.utc)
                job.execution_time = (job.completed_at - job.started_at).total_seconds()

                # Cleanup stale session (removes from self.sessions and self.connections)
                await self.disconnect_session(node_name)

                # Raise informative error
                raise RuntimeError(
                    f"SSH session closed for {node_name}. "
                    "Session removed. Please reconnect with ssh_configure()."
                )

            # Other errors - just mark job as failed
            job.status = "failed"
            job.error = error_str
            job.completed_at = datetime.now(timezone.utc)
            job.execution_time = (job.completed_at - job.started_at).total_seconds()

            logger.error(f"Command failed: {node_name} - {command}: {e}")
            raise

    # ========================================================================
    # Config Commands
    # ========================================================================

    async def send_config_set_adaptive(
        self,
        node_name: str,
        config_commands: list,
        wait_timeout: int,
        exit_config_mode: bool
    ) -> Dict:
        """Execute config commands with adaptive async"""
        if node_name not in self.sessions:
            raise ValueError(f"No session for {node_name}")

        session = self.sessions[node_name]
        connection = self.connections[node_name]

        # Update activity timestamp (v0.1.6)
        self._update_activity(node_name)

        # Create Job
        command_str = "\n".join(config_commands)
        job = Job(
            job_id=str(uuid.uuid4()),
            node_name=node_name,
            command=f"config_set: {command_str[:100]}...",  # Truncate for display
            output="",
            status="running",
            error=None,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            execution_time=None,
            sequence_number=session.sequence_counter
        )

        session.jobs.append(job)
        session.sequence_counter += 1

        # Trim history if needed
        if len(session.jobs) > self.MAX_HISTORY_JOBS:
            session.jobs = session.jobs[-self.MAX_HISTORY_JOBS:]

        # Start command in background
        task = asyncio.create_task(
            self._execute_config_set(node_name, job.job_id, config_commands, exit_config_mode)
        )

        # Poll for wait_timeout seconds
        for i in range(wait_timeout):
            await asyncio.sleep(1)
            if task.done():
                # Command completed - get result and recalculate timing
                try:
                    output = task.result()
                    # Job object updated by background task - recalculate execution time
                    if job.completed_at and job.started_at:
                        job.execution_time = (job.completed_at - job.started_at).total_seconds()

                    return {
                        "completed": True,
                        "job_id": job.job_id,
                        "output": output,
                        "execution_time": job.execution_time,
                        "started_at": job.started_at,
                        "completed_at": job.completed_at
                    }
                except Exception as e:
                    # Config command failed or timed out
                    error_msg = str(e)
                    logger.error(f"Config failed: {error_msg}")

                    # Detect error type and provide helpful message (v0.1.6)
                    if "Socket is closed" in error_msg:
                        error_code = "SSH_DISCONNECTED"
                        suggested_action = (
                            "Session was stale and has been removed. "
                            "Reconnect with ssh_configure() and try again."
                        )
                    elif "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                        error_code = "TIMEOUT"
                        suggested_action = "Config commands timed out. Increase read_timeout or check device responsiveness."
                    else:
                        error_code = "COMMAND_FAILED"
                        suggested_action = "Check config command syntax and device state."

                    completed_at = datetime.now(timezone.utc)
                    exec_time = (completed_at - job.started_at).total_seconds()

                    return {
                        "completed": False,  # Mark as failed
                        "job_id": job.job_id,
                        "output": job.output if job.output else "",
                        "execution_time": exec_time,
                        "started_at": job.started_at,
                        "completed_at": completed_at,
                        "error": error_msg,
                        "error_code": error_code,
                        "suggested_action": suggested_action
                    }

        # Still running
        return {
            "completed": False,
            "job_id": job.job_id,
            "message": f"Config commands running. Poll GET /ssh/job/{job.job_id} for status.",
            "started_at": job.started_at
        }

    async def _execute_config_set(
        self,
        node_name: str,
        job_id: str,
        config_commands: list,
        exit_config_mode: bool
    ) -> str:
        """Execute config_set and update job"""
        session = self.sessions[node_name]
        connection = self.connections[node_name]

        job = next((j for j in session.jobs if j.job_id == job_id), None)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        try:
            output = await asyncio.to_thread(
                connection.send_config_set,
                config_commands,
                exit_config_mode=exit_config_mode
            )

            job.output = output
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.execution_time = (job.completed_at - job.started_at).total_seconds()

            await self._append_to_buffer(node_name, output)

            logger.info(f"Config commands completed: {node_name} ({job.execution_time:.2f}s)")
            return output

        except Exception as e:
            error_str = str(e)

            # Detect socket closure and cleanup stale session (v0.1.6)
            if "Socket is closed" in error_str or "Socket error" in error_str:
                logger.error(f"Stale session detected for {node_name}, cleaning up")

                # Mark job as failed
                job.status = "failed"
                job.error = "SSH connection closed - session was stale"
                job.completed_at = datetime.now(timezone.utc)
                job.execution_time = (job.completed_at - job.started_at).total_seconds()

                # Cleanup stale session
                await self.disconnect_session(node_name)

                # Raise informative error
                raise RuntimeError(
                    f"SSH session closed for {node_name}. "
                    "Session removed. Please reconnect with ssh_configure()."
                )

            # Other errors - just mark job as failed
            job.status = "failed"
            job.error = error_str
            job.completed_at = datetime.now(timezone.utc)
            job.execution_time = (job.completed_at - job.started_at).total_seconds()
            logger.error(f"Config commands failed: {node_name}: {e}")
            raise

    # ========================================================================
    # Buffer Management (Storage System 1)
    # ========================================================================

    async def _append_to_buffer(self, node_name: str, output: str):
        """Append output to continuous buffer"""
        session = self.sessions[node_name]
        session.buffer += output

        # Trim if needed
        if len(session.buffer) > self.MAX_BUFFER_SIZE:
            session.buffer = session.buffer[-self.TRIM_BUFFER_SIZE:]
            session.buffer_read_pos = 0  # Reset diff position
            logger.info(f"Buffer trimmed for {node_name}")

    def get_buffer(
        self,
        node_name: str,
        mode: str = "diff",
        pages: int = 1,
        pattern: Optional[str] = None,
        case_insensitive: bool = False,
        invert: bool = False,
        before: int = 0,
        after: int = 0,
        context: int = 0
    ) -> str:
        """
        Read continuous buffer (like console read_console)

        Modes:
        - diff: New output since last read
        - last_page: Last ~25 lines
        - num_pages: Last N pages
        - all: Entire buffer

        Grep Parameters (optional):
        - pattern: Regex pattern to filter output
        - case_insensitive: Ignore case when matching (grep -i)
        - invert: Return non-matching lines (grep -v)
        - before/after/context: Context lines around matches (grep -B/-A/-C)
        """
        if node_name not in self.sessions:
            raise ValueError(f"No session for {node_name}")

        session = self.sessions[node_name]

        # Update activity timestamp (v0.1.6)
        self._update_activity(node_name)

        # Get output based on mode
        if mode == "diff":
            # Return new output since last read
            output = session.buffer[session.buffer_read_pos:]
            session.buffer_read_pos = len(session.buffer)
            if not output:
                output = "No new output"

        elif mode == "last_page":
            # Return last ~25 lines
            lines = session.buffer.splitlines()
            output = '\n'.join(lines[-25:]) if len(lines) > 25 else session.buffer

        elif mode == "num_pages":
            # Return last N pages
            lines = session.buffer.splitlines()
            lines_to_return = 25 * pages
            output = '\n'.join(lines[-lines_to_return:]) if len(lines) > lines_to_return else session.buffer

        elif mode == "all":
            output = session.buffer

        else:
            raise ValueError(f"Invalid mode: {mode}")

        # Apply grep filter if pattern provided
        if pattern:
            output = self._grep_filter(
                output,
                pattern,
                case_insensitive=case_insensitive,
                invert=invert,
                before=before,
                after=after,
                context=context
            )

        return output

    def _grep_filter(
        self,
        text: str,
        pattern: str,
        case_insensitive: bool = False,
        invert: bool = False,
        before: int = 0,
        after: int = 0,
        context: int = 0
    ) -> str:
        """
        Filter text using grep-style pattern matching

        Args:
            text: Input text to filter
            pattern: Regex pattern to match
            case_insensitive: Ignore case when matching (grep -i)
            invert: Return non-matching lines (grep -v)
            before: Lines of context before match (grep -B)
            after: Lines of context after match (grep -A)
            context: Lines of context before AND after (grep -C, overrides before/after)

        Returns:
            Filtered lines with line numbers (grep -n format: "LINE_NUM: line content")
            Empty string if no matches
        """
        if not text:
            return ""

        # Context parameter overrides before/after
        if context > 0:
            before = after = context

        # Compile regex pattern
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        lines = text.splitlines()
        matching_indices = set()

        # Find matching lines
        for i, line in enumerate(lines):
            matches = bool(regex.search(line))
            if invert:
                matches = not matches
            if matches:
                matching_indices.add(i)

        # Add context lines
        indices_with_context = set()
        for idx in matching_indices:
            # Add lines before
            for b in range(max(0, idx - before), idx):
                indices_with_context.add(b)
            # Add matching line
            indices_with_context.add(idx)
            # Add lines after
            for a in range(idx + 1, min(len(lines), idx + after + 1)):
                indices_with_context.add(a)

        # Build output with line numbers (1-indexed, grep -n style)
        if not indices_with_context:
            return ""

        result = []
        for idx in sorted(indices_with_context):
            line_num = idx + 1  # 1-indexed line numbers
            result.append(f"{line_num}: {lines[idx]}")

        return '\n'.join(result)

    # ========================================================================
    # Command History (Storage System 2)
    # ========================================================================

    def get_history(
        self,
        node_name: str,
        limit: int = 50,
        search: Optional[str] = None
    ) -> list[JobSummary]:
        """
        Get command history in execution order

        Returns JobSummary list (abbreviated for listings)
        """
        if node_name not in self.sessions:
            raise ValueError(f"No session for {node_name}")

        session = self.sessions[node_name]
        jobs = session.jobs

        # Filter by search term
        if search:
            jobs = [j for j in jobs if search.lower() in j.command.lower()]

        # Convert to summaries
        summaries = [
            JobSummary(
                job_id=j.job_id,
                command=j.command,
                status=j.status,
                started_at=j.started_at,
                completed_at=j.completed_at,
                execution_time=j.execution_time,
                output_size=len(j.output)
            )
            for j in jobs
        ]

        # Return last N jobs
        return summaries[-limit:]

    def get_job(self, node_name: str, job_id: str) -> Optional[Job]:
        """Get specific job with full output"""
        if node_name not in self.sessions:
            raise ValueError(f"No session for {node_name}")

        session = self.sessions[node_name]
        job = next((j for j in session.jobs if j.job_id == job_id), None)
        return job

    # ========================================================================
    # Session Cleanup
    # ========================================================================

    async def cleanup_sessions(
        self,
        keep_nodes: list[str],
        clean_all: bool
    ) -> Tuple[list[str], list[str]]:
        """
        Clean orphaned/all sessions

        Returns:
            (cleaned_nodes, kept_nodes)
        """
        cleaned = []
        kept = []

        if clean_all:
            # Clean all sessions
            for node_name in list(self.sessions.keys()):
                await self.disconnect_session(node_name)
                cleaned.append(node_name)
        else:
            # Clean sessions not in keep_nodes
            for node_name in list(self.sessions.keys()):
                if node_name not in keep_nodes:
                    await self.disconnect_session(node_name)
                    cleaned.append(node_name)
                else:
                    kept.append(node_name)

        logger.info(f"Cleanup: cleaned={cleaned}, kept={kept}")
        return cleaned, kept
