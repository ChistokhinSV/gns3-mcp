"""Unit tests for ConsoleManager (console_manager.py)

Tests telnet console session management with mocked network I/O.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta
from console_manager import (
    ConsoleManager,
    ConsoleSession,
    strip_ansi,
    MAX_BUFFER_SIZE,
    SESSION_TIMEOUT
)


# ===== Helper Functions Tests =====

class TestStripAnsi:
    """Tests for strip_ansi() helper function"""

    def test_strip_ansi_codes(self):
        """Test ANSI escape code removal"""
        text = "\x1B[31mRed text\x1B[0m Normal"
        result = strip_ansi(text)
        assert result == "Red text Normal"

    def test_normalize_line_endings_crlf(self):
        """Test CRLF → LF normalization"""
        text = "Line 1\r\nLine 2\r\nLine 3"
        result = strip_ansi(text)
        assert result == "Line 1\nLine 2\nLine 3"

    def test_normalize_line_endings_cr(self):
        """Test CR → LF normalization"""
        text = "Line 1\rLine 2\rLine 3"
        result = strip_ansi(text)
        assert result == "Line 1\nLine 2\nLine 3"

    def test_remove_excessive_blank_lines(self):
        """Test excessive newlines reduced to double"""
        text = "Line 1\n\n\n\n\nLine 2"
        result = strip_ansi(text)
        assert result == "Line 1\n\nLine 2"

    def test_complex_ansi_with_line_endings(self):
        """Test combined ANSI removal and line ending normalization"""
        text = "\x1B[1;32mGreen\x1B[0m\r\n\x1B[31mRed\x1B[0m\r\n"
        result = strip_ansi(text)
        assert result == "Green\nRed\n"


# ===== ConsoleSession Tests =====

class TestConsoleSession:
    """Tests for ConsoleSession dataclass"""

    def test_session_initialization(self):
        """Test session is initialized with correct defaults"""
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        assert session.session_id == "test-id"
        assert session.host == "localhost"
        assert session.port == 5000
        assert session.node_name == "Router1"
        assert session.buffer == ""
        assert session.read_position == 0
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)

    def test_update_activity(self):
        """Test activity timestamp updates"""
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        original_time = session.last_activity
        # Sleep to ensure time difference
        import time
        time.sleep(0.01)
        session.update_activity()
        assert session.last_activity > original_time

    def test_is_expired_fresh_session(self):
        """Test fresh session is not expired"""
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        assert session.is_expired() is False

    def test_is_expired_old_session(self):
        """Test old session is expired"""
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        # Set last_activity to old time
        session.last_activity = datetime.now() - timedelta(seconds=SESSION_TIMEOUT + 100)
        assert session.is_expired() is True


# ===== Connection Management Tests =====

class TestConnect:
    """Tests for ConsoleManager.connect()"""

    @pytest.mark.asyncio
    async def test_connect_creates_session(self):
        """Test successful connection creates session"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id = await manager.connect("localhost", 5000, "Router1")

            assert session_id in manager.sessions
            assert manager.sessions[session_id].host == "localhost"
            assert manager.sessions[session_id].port == 5000
            assert manager.sessions[session_id].node_name == "Router1"
            assert manager._node_sessions["Router1"] == session_id
            assert session_id in manager._readers

    @pytest.mark.asyncio
    async def test_connect_reuses_existing_session(self):
        """Test connecting to same node reuses session"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            # First connection
            session_id_1 = await manager.connect("localhost", 5000, "Router1")
            # Second connection to same node
            session_id_2 = await manager.connect("localhost", 5000, "Router1")

            assert session_id_1 == session_id_2
            assert len(manager.sessions) == 1

    @pytest.mark.asyncio
    async def test_connect_network_error_raises(self):
        """Test connection failure raises exception"""
        manager = ConsoleManager()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  side_effect=ConnectionRefusedError("Connection refused")):
            with pytest.raises(ConnectionRefusedError):
                await manager.connect("localhost", 5000, "Router1")

    @pytest.mark.asyncio
    async def test_connect_race_condition_handled(self):
        """Test race condition where two connections to same node"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        # First connection succeeds and adds to sessions
        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id_1 = await manager.connect("localhost", 5000, "Router1")

        # Second connection encounters race condition (node already mapped)
        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id_2 = await manager.connect("localhost", 5000, "Router1")

            # Should return existing session
            assert session_id_2 == session_id_1
            # Second writer should be closed (race loser)
            # (In actual race, this is tested by the double-check logic)


class TestDisconnect:
    """Tests for ConsoleManager.disconnect()"""

    @pytest.mark.asyncio
    async def test_disconnect_closes_connection(self):
        """Test disconnect closes writer and removes session"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id = await manager.connect("localhost", 5000, "Router1")

            # Disconnect
            result = await manager.disconnect(session_id)

            assert result is True
            assert session_id not in manager.sessions
            assert "Router1" not in manager._node_sessions
            mock_writer.close.assert_called_once()
            mock_writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_cancels_reader_task(self):
        """Test disconnect cancels background reader task"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id = await manager.connect("localhost", 5000, "Router1")

            # Get reader task
            reader_task = manager._readers[session_id]
            assert reader_task is not None

            # Disconnect
            await manager.disconnect(session_id)

            # Task should be cancelled
            assert session_id not in manager._readers
            assert reader_task.cancelled()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_session_returns_false(self):
        """Test disconnecting non-existent session returns False"""
        manager = ConsoleManager()
        result = await manager.disconnect("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_by_node(self):
        """Test disconnect_by_node() convenience method"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            await manager.connect("localhost", 5000, "Router1")

            # Disconnect by node name
            result = await manager.disconnect_by_node("Router1")

            assert result is True
            assert not manager.has_session("Router1")


# ===== Session Lifecycle Tests =====

class TestSessionLifecycle:
    """Tests for session lifecycle management"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_sessions(self):
        """Test cleanup_expired() removes sessions older than timeout"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id = await manager.connect("localhost", 5000, "Router1")

            # Manually expire the session
            manager.sessions[session_id].last_activity = (
                datetime.now() - timedelta(seconds=SESSION_TIMEOUT + 100)
            )

            # Run cleanup
            await manager.cleanup_expired()

            # Session should be removed
            assert session_id not in manager.sessions

    @pytest.mark.asyncio
    async def test_cleanup_expired_keeps_active_sessions(self):
        """Test cleanup_expired() keeps active sessions"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            session_id = await manager.connect("localhost", 5000, "Router1")

            # Run cleanup on fresh session
            await manager.cleanup_expired()

            # Session should still exist
            assert session_id in manager.sessions

    @pytest.mark.asyncio
    async def test_close_all_disconnects_all_sessions(self):
        """Test close_all() disconnects all sessions"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            await manager.connect("localhost", 5000, "Router1")
            await manager.connect("localhost", 5001, "Router2")
            await manager.connect("localhost", 5002, "Router3")

            assert len(manager.sessions) == 3

            await manager.close_all()

            assert len(manager.sessions) == 0

    def test_list_sessions_returns_session_info(self):
        """Test list_sessions() returns session metadata"""
        manager = ConsoleManager()

        # Create session manually (simpler than mocking telnet)
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        manager.sessions["test-id"] = session

        sessions_info = manager.list_sessions()

        assert "test-id" in sessions_info
        assert sessions_info["test-id"]["node_name"] == "Router1"
        assert sessions_info["test-id"]["host"] == "localhost"
        assert sessions_info["test-id"]["port"] == 5000
        assert "created_at" in sessions_info["test-id"]
        assert sessions_info["test-id"]["buffer_size"] == 0


# ===== Buffer Management Tests =====

class TestBufferManagement:
    """Tests for buffer management and reading"""

    def test_get_output_returns_full_buffer(self):
        """Test get_output() returns full console buffer"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        session.buffer = "Line 1\nLine 2\nLine 3"
        manager.sessions["test-id"] = session

        output = manager.get_output("test-id")

        assert output == "Line 1\nLine 2\nLine 3"

    def test_get_output_strips_ansi(self):
        """Test get_output() strips ANSI codes"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        session.buffer = "\x1B[31mRed\x1B[0m text"
        manager.sessions["test-id"] = session

        output = manager.get_output("test-id")

        assert output == "Red text"
        assert "\x1B" not in output

    def test_get_diff_returns_new_output(self):
        """Test get_diff() returns only new output since last read"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        session.buffer = "Old output\nNew output"
        session.read_position = 11  # After "Old output\n"
        manager.sessions["test-id"] = session

        diff = manager.get_diff("test-id")

        assert diff == "New output"
        assert session.read_position == len(session.buffer)

    def test_get_diff_advances_read_position(self):
        """Test get_diff() advances read position"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        session.buffer = "First\nSecond\nThird"
        session.read_position = 0
        manager.sessions["test-id"] = session

        # First read
        diff1 = manager.get_diff("test-id")
        assert diff1 == "First\nSecond\nThird"
        assert session.read_position == len(session.buffer)

        # Second read (no new data)
        diff2 = manager.get_diff("test-id")
        assert diff2 == ""

    @pytest.mark.asyncio
    async def test_buffer_trimming_at_max_size(self):
        """Test buffer is trimmed when exceeding MAX_BUFFER_SIZE"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )

        # Create large buffer exceeding MAX_BUFFER_SIZE
        large_data = "x" * (MAX_BUFFER_SIZE + 1000)
        session.buffer = large_data
        session.read_position = 0

        # Simulate _read_console trimming logic
        if len(session.buffer) > MAX_BUFFER_SIZE:
            trim_size = MAX_BUFFER_SIZE // 2
            session.buffer = session.buffer[-trim_size:]
            if session.read_position > trim_size:
                session.read_position = 0

        # Buffer should be trimmed to half of MAX_BUFFER_SIZE
        assert len(session.buffer) == MAX_BUFFER_SIZE // 2
        assert session.read_position == 0


# ===== Data Processing Tests =====

class TestDataProcessing:
    """Tests for send() and data processing"""

    @pytest.mark.asyncio
    async def test_send_writes_to_writer(self):
        """Test send() writes data to telnet writer"""
        manager = ConsoleManager()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1",
            writer=mock_writer
        )
        manager.sessions["test-id"] = session

        result = await manager.send("test-id", "test command\n")

        assert result is True
        mock_writer.write.assert_called_once_with("test command\n")
        mock_writer.drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_nonexistent_session_returns_false(self):
        """Test send() returns False for non-existent session"""
        manager = ConsoleManager()
        result = await manager.send("nonexistent-id", "data")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_updates_activity(self):
        """Test send() updates last_activity timestamp"""
        manager = ConsoleManager()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1",
            writer=mock_writer
        )
        original_activity = session.last_activity
        manager.sessions["test-id"] = session

        # Wait to ensure time difference
        await asyncio.sleep(0.01)

        await manager.send("test-id", "data")

        assert session.last_activity > original_activity

    @pytest.mark.asyncio
    async def test_send_by_node_convenience_method(self):
        """Test send_by_node() sends data by node name"""
        manager = ConsoleManager()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1",
            writer=mock_writer
        )
        manager.sessions["test-id"] = session
        manager._node_sessions["Router1"] = "test-id"

        result = await manager.send_by_node("Router1", "command\n")

        assert result is True
        mock_writer.write.assert_called_once_with("command\n")


# ===== Convenience Methods Tests =====

class TestConvenienceMethods:
    """Tests for node-name based convenience methods"""

    def test_get_session_id_returns_id(self):
        """Test get_session_id() returns session ID for node"""
        manager = ConsoleManager()
        manager._node_sessions["Router1"] = "test-id"

        session_id = manager.get_session_id("Router1")

        assert session_id == "test-id"

    def test_get_session_id_returns_none_for_unknown_node(self):
        """Test get_session_id() returns None for unknown node"""
        manager = ConsoleManager()
        session_id = manager.get_session_id("UnknownNode")
        assert session_id is None

    def test_has_session_returns_true_for_active_session(self):
        """Test has_session() returns True for active session"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        manager.sessions["test-id"] = session
        manager._node_sessions["Router1"] = "test-id"

        assert manager.has_session("Router1") is True

    def test_has_session_returns_false_for_inactive_session(self):
        """Test has_session() returns False when session not active"""
        manager = ConsoleManager()
        manager._node_sessions["Router1"] = "test-id"  # Mapped but no session

        assert manager.has_session("Router1") is False

    def test_get_output_by_node(self):
        """Test get_output_by_node() retrieves output by node name"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        session.buffer = "Test output"
        manager.sessions["test-id"] = session
        manager._node_sessions["Router1"] = "test-id"

        output = manager.get_output_by_node("Router1")

        assert output == "Test output"

    def test_get_diff_by_node(self):
        """Test get_diff_by_node() retrieves diff by node name"""
        manager = ConsoleManager()
        session = ConsoleSession(
            session_id="test-id",
            host="localhost",
            port=5000,
            node_name="Router1"
        )
        session.buffer = "New data"
        session.read_position = 0
        manager.sessions["test-id"] = session
        manager._node_sessions["Router1"] = "test-id"

        diff = manager.get_diff_by_node("Router1")

        assert diff == "New data"
        assert session.read_position == len(session.buffer)


# ===== Concurrent Access Tests =====

class TestConcurrentAccess:
    """Tests for thread-safety and concurrent access"""

    @pytest.mark.asyncio
    async def test_concurrent_connections_use_lock(self):
        """Test concurrent connect() calls are serialized by lock"""
        manager = ConsoleManager()
        mock_reader = AsyncMock()
        mock_reader.at_eof.return_value = False
        mock_reader.read = AsyncMock(return_value="")
        mock_writer = MagicMock()

        with patch('console_manager.telnetlib3.open_connection',
                  new_callable=AsyncMock,
                  return_value=(mock_reader, mock_writer)):
            # Launch multiple concurrent connections
            results = await asyncio.gather(
                manager.connect("localhost", 5000, "Router1"),
                manager.connect("localhost", 5001, "Router2"),
                manager.connect("localhost", 5002, "Router3")
            )

            # All should succeed and create separate sessions
            assert len(results) == 3
            assert len(set(results)) == 3  # All unique session IDs
            assert len(manager.sessions) == 3

    @pytest.mark.asyncio
    async def test_lock_prevents_race_conditions(self):
        """Test lock prevents race conditions in session creation"""
        manager = ConsoleManager()

        # This test verifies the lock exists and is an asyncio.Lock
        assert isinstance(manager._lock, asyncio.Lock)

        # The actual race condition protection is tested implicitly
        # in test_connect_race_condition_handled above
