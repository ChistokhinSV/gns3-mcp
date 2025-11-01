"""Console management tools for GNS3 MCP Server

Provides tools for interacting with node consoles via telnet.
"""

import asyncio
import json
import re
import time
from typing import TYPE_CHECKING

from error_utils import (
    console_connection_failed_error,
    create_error_response,
    node_not_found_error,
    node_stopped_error,
    project_not_found_error,
    validation_error,
)
from models import ConsoleStatus, ErrorCode

if TYPE_CHECKING:
    from main import AppContext


async def _auto_connect_console(app: "AppContext", node_name: str) -> str | None:
    """Auto-connect to console if not already connected

    Returns:
        JSON error message if connection fails, None if successful
    """
    # Check if already connected
    if app.console.has_session(node_name):
        return None

    if not app.current_project_id:
        return project_not_found_error()

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n["name"] == node_name), None)

    if not node:
        available_nodes = [n["name"] for n in nodes]
        return node_not_found_error(
            node_name=node_name, project_id=app.current_project_id, available_nodes=available_nodes
        )

    # Check console type
    console_type = node["console_type"]
    if console_type not in ["telnet"]:
        return validation_error(
            message=f"Console type '{console_type}' not supported",
            parameter="console_type",
            value=console_type,
            valid_values=["telnet"],
        )

    if not node["console"]:
        return node_stopped_error(node_name=node_name, operation="console access")

    # Extract host from GNS3 client config
    host = app.gns3.base_url.split("//")[1].split(":")[0]
    port = node["console"]

    # Connect
    try:
        await app.console.connect(host, port, node_name)
        return None
    except Exception as e:
        return console_connection_failed_error(
            node_name=node_name, host=host, port=port, details=str(e)
        )


async def send_console_impl(app: "AppContext", node_name: str, data: str, raw: bool = False) -> str:
    """Send data to console (auto-connects if needed)

    Sends data immediately to console without waiting for response.
    For interactive workflows, use read_console() after sending to verify output.

    Timing Considerations:
    - Console output appears in background buffer (read via read_console)
    - Allow 0.5-2 seconds after send before reading for command processing
    - Interactive prompts (login, password) may need 1-3 seconds to appear
    - Boot/initialization sequences may take 30-60 seconds

    Auto-connect Behavior:
    - First send/read automatically connects to console (no manual connect needed)
    - Connection persists until disconnect_console() or 30-minute timeout
    - Check connection state with get_console_status()

    Escape Sequence Processing:
    - By default, processes common escape sequences (\n, \r, \t, \x1b)
    - Use raw=True to send data without processing (for binary data)

    Args:
        node_name: Name of the node (e.g., "Router1")
        data: Data to send - include newline for commands (e.g., "enable\n")
              Send just "\n" to wake console and check for prompts
        raw: If True, send data without escape sequence processing (default: False)

    Returns:
        "Sent successfully" or error message

    Example - Wake console and check state:
        send_console("R1", "\n")
        await 1 second
        read_console("R1", diff=True)  # See what prompt appeared
    """
    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    # Check if terminal has been accessed (read) before sending
    if not app.console.has_accessed_terminal_by_node(node_name):
        return create_error_response(
            error=f"Cannot send to console for node '{node_name}' - terminal not accessed yet",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details="You must read the console first to understand the current terminal state (prompt, login screen, etc.) before sending commands",
            suggested_action="Use console_read() with mode='diff' or mode='last_page' to check the current terminal state, then retry sending",
            context={"node_name": node_name, "reason": "terminal_not_accessed"},
        )

    # Process escape sequences unless raw mode
    if not raw:
        # First handle escape sequences (backslash-escaped strings)
        data = data.replace("\\r\\n", "\r\n")  # \r\n → CR+LF
        data = data.replace("\\n", "\n")  # \n → LF
        data = data.replace("\\r", "\r")  # \r → CR
        data = data.replace("\\t", "\t")  # \t → tab
        data = data.replace("\\x1b", "\x1b")  # \x1b → ESC

        # Then normalize all newlines to LF for Unix/Linux compatibility
        # This handles copy-pasted multi-line text
        data = data.replace("\r\n", "\n")  # Normalize CRLF to LF
        data = data.replace("\r", "\n")  # Normalize CR to LF
        # Note: Don't convert to CRLF - Unix/Linux devices expect LF only
        # Windows/Cisco devices handle LF correctly via telnet protocol

    success = await app.console.send_by_node(node_name, data)
    if success:
        return "Sent successfully"
    else:
        return create_error_response(
            error=f"Failed to send data to console for node '{node_name}'",
            error_code=ErrorCode.CONSOLE_DISCONNECTED.value,
            details="Console session may have been disconnected",
            suggested_action="Check console connection with get_console_status(), or use disconnect_console() and retry",
            context={"node_name": node_name},
        )


async def read_console_impl(
    app: "AppContext",
    node_name: str,
    mode: str = "diff",
    pages: int = 1,
    pattern: str | None = None,
    case_insensitive: bool = False,
    invert: bool = False,
    before: int = 0,
    after: int = 0,
    context: int = 0,
) -> str:
    """Read console output (auto-connects if needed)

    Reads accumulated output from background console buffer. Output accumulates
    while device runs - this function retrieves it without blocking.

    Buffer Behavior:
    - Background task continuously reads console into 10MB buffer
    - Diff mode (DEFAULT): Returns only NEW output since last read
    - Last page mode: Returns last ~25 lines of buffer
    - Num pages mode: Returns last N pages (~25 lines per page)
    - All mode: Returns ALL console output since connection (WARNING: May produce >25000 tokens!)
    - Read position advances with each diff mode read

    Timing Recommendations:
    - After send_console(): Wait 0.5-2s before reading for command output
    - After node start: Wait 30-60s for boot messages
    - Interactive prompts: Wait 1-3s for prompt to appear

    State Detection Tips:
    - Look for prompt patterns: "Router>", "Login:", "Password:", "#"
    - Check for "% " at start of line (IOS error messages)
    - Look for "[OK]" or "failed" for command results
    - MikroTik prompts: "[admin@RouterOS] > " or similar

    Args:
        node_name: Name of the node
        mode: Output mode (default: "diff")
            - "diff": Return only new output since last read (DEFAULT)
            - "last_page": Return last ~25 lines of buffer
            - "num_pages": Return last N pages (use 'pages' parameter)
            - "all": Return entire buffer (WARNING: Use carefully! May produce >25000 tokens.
                     Consider using mode="num_pages" with a specific number of pages instead.)
        pages: Number of pages to return (only valid with mode="num_pages", default: 1)
               Each page contains ~25 lines. ERROR if used with other modes.

    Returns:
        Console output (ANSI escape codes stripped, line endings normalized)
        or "No output available" if buffer empty

    Example - Interactive session (default):
        output = read_console("R1")  # mode="diff" by default
        if "Login:" in output:
            send_console("R1", "admin\\n")

    Example - Check recent output:
        output = read_console("R1", mode="last_page")  # Last 25 lines

    Example - Get multiple pages:
        output = read_console("R1", mode="num_pages", pages=3)  # Last 75 lines

    Example - Get everything (use carefully):
        output = read_console("R1", mode="all")  # Entire buffer - may be huge!
    """
    # Validate pages parameter is only used with num_pages mode
    if pages != 1 and mode != "num_pages":
        return create_error_response(
            error="Invalid parameter combination",
            error_code=ErrorCode.INVALID_PARAMETER.value,
            details=f"'pages' parameter (value: {pages}) can only be used with mode='num_pages' (current mode: '{mode}')",
            suggested_action="Either change mode to 'num_pages' or remove the 'pages' parameter",
            context={"mode": mode, "pages": pages},
        )

    # Validate mode parameter
    if mode not in ("diff", "last_page", "num_pages", "all"):
        return validation_error(
            message=f"Invalid mode '{mode}'",
            parameter="mode",
            value=mode,
            valid_values=["diff", "last_page", "num_pages", "all"],
        )

    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    if mode == "diff":
        # Return only new output since last read
        output = app.console.get_diff_by_node(node_name)
    elif mode == "last_page":
        # Return last ~25 lines
        full_output = app.console.get_output_by_node(node_name)
        if full_output:
            lines = full_output.splitlines()
            output = "\n".join(lines[-25:]) if len(lines) > 25 else full_output
        else:
            output = None
    elif mode == "num_pages":
        # Return last N pages (~25 lines per page)
        full_output = app.console.get_output_by_node(node_name)
        if full_output:
            lines = full_output.splitlines()
            lines_to_return = 25 * pages
            output = (
                "\n".join(lines[-lines_to_return:]) if len(lines) > lines_to_return else full_output
            )
        else:
            output = None
    else:  # mode == "all"
        # Return entire buffer
        output = app.console.get_output_by_node(node_name)

    # Apply grep filter if pattern provided
    if pattern and output:
        output = _grep_filter(
            output,
            pattern,
            case_insensitive=case_insensitive,
            invert=invert,
            before=before,
            after=after,
            context=context,
        )

    return output if output is not None else "No output available"


def _grep_filter(
    text: str,
    pattern: str,
    case_insensitive: bool = False,
    invert: bool = False,
    before: int = 0,
    after: int = 0,
    context: int = 0,
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

    return "\n".join(result)


async def disconnect_console_impl(app: "AppContext", node_name: str) -> str:
    """Disconnect console session

    Args:
        node_name: Name of the node

    Returns:
        JSON with status
    """
    success = await app.console.disconnect_by_node(node_name)

    return json.dumps(
        {
            "success": success,
            "node_name": node_name,
            "message": (
                "Disconnected successfully" if success else "No active session for this node"
            ),
        },
        indent=2,
    )


async def get_console_status_impl(app: "AppContext", node_name: str) -> str:
    """Check console connection status for a node

    Shows connection state and buffer size. Does NOT show current prompt or
    device readiness - use read_console(diff=True) to check current state.

    Returns:
        JSON with ConsoleStatus:
        {
            "connected": true/false,
            "node_name": "Router1",
            "session_id": "uuid",  # null if not connected
            "host": "192.168.1.20",  # null if not connected
            "port": 5000,  # null if not connected
            "buffer_size": 1024,  # bytes accumulated
            "created_at": "2025-10-23T10:30:00"  # null if not connected
        }

    Use Cases:
    - Check if already connected before manual operations
    - Verify auto-connect succeeded
    - Monitor buffer size (>10MB triggers trim to 5MB)

    Note: Connection state does NOT indicate device readiness. A connected
    console may still be at login prompt, booting, or waiting for input.
    Use read_console() to check current prompt state.

    Args:
        node_name: Name of the node

    Example:
        status = get_console_status("R1")
        if status["connected"]:
            print(f"Buffer size: {status['buffer_size']} bytes")
        else:
            print("Not connected - next send/read will auto-connect")
    """
    if app.console.has_session(node_name):
        session_id = app.console.get_session_id(node_name)
        sessions = app.console.list_sessions()
        session_info = sessions.get(session_id, {})

        status = ConsoleStatus(
            connected=True,
            node_name=node_name,
            session_id=session_id,
            host=session_info.get("host"),
            port=session_info.get("port"),
            buffer_size=session_info.get("buffer_size"),
            created_at=session_info.get("created_at"),
        )
    else:
        status = ConsoleStatus(connected=False, node_name=node_name)

    return json.dumps(status.model_dump(), indent=2)


async def send_and_wait_console_impl(
    app: "AppContext",
    node_name: str,
    command: str,
    wait_pattern: str | None = None,
    timeout: int = 30,
    raw: bool = False,
) -> str:
    """Send command and wait for specific prompt pattern

    Combines send + wait + read into single operation. Useful for interactive
    workflows where you need to verify prompt before proceeding.

    BEST PRACTICE: Before using this tool, first check what the prompt looks like:
    1. Send "\n" with send_console() to wake the console
    2. Use read_console() to see the current prompt (e.g., "Router#", "[admin@MikroTik] >")
    3. Use that exact prompt pattern in wait_pattern parameter
    4. This ensures you wait for the right prompt and don't miss command output

    Workflow:
    1. Send command to console
    2. If wait_pattern provided: poll console until pattern appears or timeout
    3. Return all output accumulated during wait

    Args:
        node_name: Name of the node
        command: Command to send (include \n for newline)
        wait_pattern: Optional regex pattern to wait for (e.g., "Router[>#]", "Login:")
                      If None, waits 2 seconds and returns output
                      TIP: Check prompt first with read_console() to get exact pattern
        timeout: Maximum seconds to wait for pattern (default: 30)
        raw: If True, send command without escape sequence processing (default: False)

    Returns:
        JSON with:
        {
            "output": "console output",
            "pattern_found": true/false,
            "timeout_occurred": true/false,
            "wait_time": 2.5  # seconds actually waited
        }

    Example - Best practice workflow:
        # Step 1: Check the prompt first
        send_console("R1", "\n")
        output = read_console("R1")  # Shows "Router#"

        # Step 2: Use that prompt pattern
        result = send_and_wait_console(
            "R1",
            "show ip interface brief\n",
            wait_pattern="Router#",  # Wait for exact prompt
            timeout=10
        )
        # Returns when "Router#" appears - command is complete

    Example - Wait for login prompt:
        result = send_and_wait_console(
            "R1",
            "\n",
            wait_pattern="Login:",
            timeout=10
        )
        # Returns when "Login:" appears or after 10 seconds

    Example - No pattern (just wait 2s):
        result = send_and_wait_console("R1", "enable\n")
        # Sends command, waits 2s, returns output
    """
    # Auto-connect
    error = await _auto_connect_console(app, node_name)
    if error:
        return json.dumps(
            {"error": error, "output": "", "pattern_found": False, "timeout_occurred": False},
            indent=2,
        )

    # Check if terminal has been accessed (read) before sending
    if not app.console.has_accessed_terminal_by_node(node_name):
        return create_error_response(
            error=f"Cannot send to console for node '{node_name}' - terminal not accessed yet",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details="You must read the console first to understand the current terminal state (prompt, login screen, etc.) before sending commands",
            suggested_action="Use console_read() with mode='diff' or mode='last_page' to check the current terminal state, then retry sending",
            context={"node_name": node_name, "reason": "terminal_not_accessed"},
        )

    # Process escape sequences unless raw mode
    if not raw:
        # First handle escape sequences (backslash-escaped strings)
        command = command.replace("\\r\\n", "\r\n")  # \r\n → CR+LF
        command = command.replace("\\n", "\n")  # \n → LF
        command = command.replace("\\r", "\r")  # \r → CR
        command = command.replace("\\t", "\t")  # \t → tab
        command = command.replace("\\x1b", "\x1b")  # \x1b → ESC

        # Then normalize all newlines to \r\n for console compatibility
        command = command.replace("\r\n", "\n")  # Normalize CRLF to LF first
        command = command.replace("\r", "\n")  # Normalize CR to LF
        command = command.replace("\n", "\r\n")  # Convert all LF to CRLF

    # Send command
    success = await app.console.send_by_node(node_name, command)
    if not success:
        return create_error_response(
            error=f"Failed to send command to console for node '{node_name}'",
            error_code=ErrorCode.CONSOLE_DISCONNECTED.value,
            details="Console session may have been disconnected",
            suggested_action="Check console connection with get_console_status(), or use disconnect_console() and retry",
            context={"node_name": node_name, "command": command[:100]},  # Truncate long commands
        )

    # Wait for pattern or timeout
    start_time = time.time()
    pattern_found = False
    timeout_occurred = False
    accumulated_output = []  # Accumulate all output chunks

    if wait_pattern:
        try:
            pattern_re = re.compile(wait_pattern)
        except re.error as e:
            return create_error_response(
                error=f"Invalid regex pattern: {str(e)}",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details=f"Pattern '{wait_pattern}' is not a valid regular expression",
                suggested_action="Check regex syntax and escape special characters",
                context={"wait_pattern": wait_pattern, "regex_error": str(e)},
            )

        # Poll console every 0.5s
        while (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
            chunk = app.console.get_diff_by_node(node_name) or ""

            if chunk:
                accumulated_output.append(chunk)

            # Search the complete accumulated output so far
            full_output_so_far = "".join(accumulated_output)
            if pattern_re.search(full_output_so_far):
                pattern_found = True
                break

        if not pattern_found:
            timeout_occurred = True
            # Get any remaining output after timeout
            final_chunk = app.console.get_diff_by_node(node_name) or ""
            if final_chunk:
                accumulated_output.append(final_chunk)
    else:
        # No pattern - just wait 2 seconds
        await asyncio.sleep(2)
        # Collect output after waiting
        output_chunk = app.console.get_diff_by_node(node_name) or ""
        if output_chunk:
            accumulated_output.append(output_chunk)

    wait_time = time.time() - start_time

    # Return all accumulated output
    final_output = "".join(accumulated_output)

    return json.dumps(
        {
            "output": final_output,
            "pattern_found": pattern_found,
            "timeout_occurred": timeout_occurred,
            "wait_time": round(wait_time, 2),
        },
        indent=2,
    )


async def send_keystroke_impl(app: "AppContext", node_name: str, key: str) -> str:
    """Send special keystroke to console (auto-connects if needed)

    Sends special keys like arrows, function keys, control sequences for
    navigating menus, editing in vim, or TUI applications.

    Supported Keys:
    - Navigation: "up", "down", "left", "right", "home", "end", "pageup", "pagedown"
    - Editing: "enter", "backspace", "delete", "tab", "esc"
    - Control: "ctrl_c", "ctrl_d", "ctrl_z", "ctrl_a", "ctrl_e"
    - Function: "f1" through "f12"

    Args:
        node_name: Name of the node
        key: Special key to send (e.g., "up", "enter", "ctrl_c")

    Returns:
        "Sent successfully" or error message

    Example - Navigate menu:
        send_keystroke("R1", "down")
        send_keystroke("R1", "down")
        send_keystroke("R1", "enter")

    Example - Exit vim:
        send_keystroke("R1", "esc")
        send_console("R1", ":wq\n")
    """
    # Auto-connect if needed
    error = await _auto_connect_console(app, node_name)
    if error:
        return error

    # Check if terminal has been accessed (read) before sending
    if not app.console.has_accessed_terminal_by_node(node_name):
        return create_error_response(
            error=f"Cannot send keystroke to console for node '{node_name}' - terminal not accessed yet",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details="You must read the console first to understand the current terminal state (prompt, login screen, etc.) before sending keystrokes",
            suggested_action="Use console_read() with mode='diff' or mode='last_page' to check the current terminal state, then retry sending",
            context={"node_name": node_name, "reason": "terminal_not_accessed"},
        )

    # Map key names to escape sequences
    SPECIAL_KEYS = {
        # Navigation
        "up": "\x1b[A",
        "down": "\x1b[B",
        "right": "\x1b[C",
        "left": "\x1b[D",
        "home": "\x1b[H",
        "end": "\x1b[F",
        "pageup": "\x1b[5~",
        "pagedown": "\x1b[6~",
        # Editing
        "enter": "\r\n",
        "backspace": "\x7f",
        "delete": "\x1b[3~",
        "tab": "\t",
        "esc": "\x1b",
        # Control sequences
        "ctrl_c": "\x03",
        "ctrl_d": "\x04",
        "ctrl_z": "\x1a",
        "ctrl_a": "\x01",
        "ctrl_e": "\x05",
        # Function keys
        "f1": "\x1bOP",
        "f2": "\x1bOQ",
        "f3": "\x1bOR",
        "f4": "\x1bOS",
        "f5": "\x1b[15~",
        "f6": "\x1b[17~",
        "f7": "\x1b[18~",
        "f8": "\x1b[19~",
        "f9": "\x1b[20~",
        "f10": "\x1b[21~",
        "f11": "\x1b[23~",
        "f12": "\x1b[24~",
    }

    key_lower = key.lower()
    if key_lower not in SPECIAL_KEYS:
        return validation_error(
            message=f"Unknown key '{key}'",
            parameter="key",
            value=key,
            valid_values=sorted(SPECIAL_KEYS.keys()),
        )

    keystroke = SPECIAL_KEYS[key_lower]
    success = await app.console.send_by_node(node_name, keystroke)
    if success:
        return "Sent successfully"
    else:
        return create_error_response(
            error=f"Failed to send keystroke to console for node '{node_name}'",
            error_code=ErrorCode.CONSOLE_DISCONNECTED.value,
            details="Console session may have been disconnected",
            suggested_action="Check console connection with get_console_status(), or use disconnect_console() and retry",
            context={"node_name": node_name, "key": key},
        )


async def console_batch_impl(app: "AppContext", operations: list[dict]) -> str:
    """Execute multiple console operations in batch with validation

    Two-phase execution:
    1. VALIDATE ALL operations (check nodes exist, required params present)
    2. EXECUTE ALL operations (only if all valid, sequential execution)

    Args:
        app: Application context
        operations: List of operation dicts, each containing:
            {
                "type": "send" | "send_and_wait" | "read" | "keystroke",
                "node_name": "NodeName",
                ...other parameters specific to operation type
            }

            Operation types and their parameters:

            - "send": Send data to console
                node_name (str): Node name
                data (str): Data to send
                raw (bool, optional): Send without escape sequence processing

            - "send_and_wait": Send command and wait for pattern
                node_name (str): Node name
                command (str): Command to send
                wait_pattern (str, optional): Regex pattern to wait for
                timeout (int, optional): Max seconds to wait
                raw (bool, optional): Send without escape sequence processing

            - "read": Read console output
                node_name (str): Node name
                mode (str, optional): "diff" (default), "last_page", "num_pages", "all"
                pages (int, optional): Number of pages (only with mode="num_pages")
                pattern (str, optional): Grep regex pattern
                case_insensitive (bool, optional): Case insensitive grep
                invert (bool, optional): Invert grep match
                before (int, optional): Context lines before match
                after (int, optional): Context lines after match
                context (int, optional): Context lines before AND after

            - "keystroke": Send special keystroke
                node_name (str): Node name
                key (str): Key to send (up, down, enter, ctrl_c, etc.)

    Returns:
        JSON with execution results:
        {
            "completed": [0, 1, 2],  // Indices of successful operations
            "failed": [3],  // Indices of failed operations
            "results": [
                {
                    "operation_index": 0,
                    "success": true,
                    "operation_type": "send_and_wait",
                    "node_name": "R1",
                    "result": {...}  // Operation-specific result
                },
                ...
            ],
            "total_operations": 4,
            "execution_time": 5.3
        }
    """
    import time

    start_time = time.time()

    # Validation: Check all operations first
    VALID_TYPES = {"send", "send_and_wait", "read", "keystroke"}

    for idx, op in enumerate(operations):
        # Check required fields
        if "type" not in op:
            return validation_error(
                parameter="operations",
                details=f"Operation {idx} missing required field 'type'",
                valid_values=list(VALID_TYPES),
            )

        if op["type"] not in VALID_TYPES:
            return validation_error(
                parameter=f"operations[{idx}].type",
                details=f"Invalid operation type: {op['type']}",
                valid_values=list(VALID_TYPES),
            )

        if "node_name" not in op:
            return create_error_response(
                error=f"Operation {idx} missing required field 'node_name'",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details="All operations must specify 'node_name'",
                suggested_action="Add 'node_name' field to operation",
                context={"operation_index": idx, "operation": op},
            )

        # Type-specific validation
        op_type = op["type"]
        node_name = op["node_name"]

        if op_type == "send":
            if "data" not in op:
                return create_error_response(
                    error=f"Operation {idx} (type='send') missing required parameter 'data'",
                    error_code=ErrorCode.INVALID_PARAMETER.value,
                    details="send operations require 'data' parameter",
                    suggested_action="Add 'data' field to operation",
                    context={"operation_index": idx, "node_name": node_name},
                )

        elif op_type == "send_and_wait":
            if "command" not in op:
                return create_error_response(
                    error=f"Operation {idx} (type='send_and_wait') missing required parameter 'command'",
                    error_code=ErrorCode.INVALID_PARAMETER.value,
                    details="send_and_wait operations require 'command' parameter",
                    suggested_action="Add 'command' field to operation",
                    context={"operation_index": idx, "node_name": node_name},
                )

        elif op_type == "keystroke":
            if "key" not in op:
                return create_error_response(
                    error=f"Operation {idx} (type='keystroke') missing required parameter 'key'",
                    error_code=ErrorCode.INVALID_PARAMETER.value,
                    details="keystroke operations require 'key' parameter",
                    suggested_action="Add 'key' field to operation",
                    context={"operation_index": idx, "node_name": node_name},
                )

    # Validation passed - execute all operations sequentially
    results = []
    completed_indices = []
    failed_indices = []

    for idx, op in enumerate(operations):
        op_type = op["type"]
        node_name = op["node_name"]

        try:
            # Execute operation based on type
            if op_type == "send":
                result = await send_console_impl(app, node_name, op["data"], op.get("raw", False))

            elif op_type == "send_and_wait":
                result = await send_and_wait_console_impl(
                    app,
                    node_name,
                    op["command"],
                    op.get("wait_pattern"),
                    op.get("timeout", 30),
                    op.get("raw", False),
                )

            elif op_type == "read":
                result = await read_console_impl(
                    app,
                    node_name,
                    op.get("mode", "diff"),
                    op.get("pages", 1),
                    op.get("pattern"),
                    op.get("case_insensitive", False),
                    op.get("invert", False),
                    op.get("before", 0),
                    op.get("after", 0),
                    op.get("context", 0),
                )

            elif op_type == "keystroke":
                result = await send_keystroke_impl(app, node_name, op["key"])

            # Check if result is an error (error responses are JSON strings with "error" field)
            try:
                result_dict = json.loads(result) if isinstance(result, str) else result
                if isinstance(result_dict, dict) and "error" in result_dict:
                    # Operation failed
                    failed_indices.append(idx)
                    results.append(
                        {
                            "operation_index": idx,
                            "success": False,
                            "operation_type": op_type,
                            "node_name": node_name,
                            "error": result_dict,
                        }
                    )
                else:
                    # Operation succeeded
                    completed_indices.append(idx)
                    results.append(
                        {
                            "operation_index": idx,
                            "success": True,
                            "operation_type": op_type,
                            "node_name": node_name,
                            "result": result_dict if isinstance(result_dict, dict) else result,
                        }
                    )
            except (json.JSONDecodeError, TypeError):
                # Non-JSON result (like "Sent successfully" string)
                completed_indices.append(idx)
                results.append(
                    {
                        "operation_index": idx,
                        "success": True,
                        "operation_type": op_type,
                        "node_name": node_name,
                        "result": result,
                    }
                )

        except Exception as e:
            # Unexpected error during execution
            failed_indices.append(idx)
            results.append(
                {
                    "operation_index": idx,
                    "success": False,
                    "operation_type": op_type,
                    "node_name": node_name,
                    "error": {
                        "error": str(e),
                        "error_code": ErrorCode.INTERNAL_ERROR.value,
                        "details": f"Unexpected error executing {op_type} operation",
                        "suggested_action": "Check operation parameters and node status",
                    },
                }
            )

    execution_time = time.time() - start_time

    return json.dumps(
        {
            "completed": completed_indices,
            "failed": failed_indices,
            "results": results,
            "total_operations": len(operations),
            "execution_time": round(execution_time, 2),
        },
        indent=2,
    )
