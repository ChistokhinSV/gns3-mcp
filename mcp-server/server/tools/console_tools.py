"""Console management tools for GNS3 MCP Server

Provides tools for interacting with node consoles via telnet.
"""
import asyncio
import json
import time
import re
from typing import TYPE_CHECKING, Optional

from models import ConsoleStatus, ErrorResponse

if TYPE_CHECKING:
    from main import AppContext


async def _auto_connect_console(app: "AppContext", node_name: str) -> Optional[str]:
    """Auto-connect to console if not already connected

    Returns:
        Error message if connection fails, None if successful
    """
    # Check if already connected
    if app.console.has_session(node_name):
        return None

    if not app.current_project_id:
        return "No project opened. Use open_project() first."

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return f"Node '{node_name}' not found. Use list_nodes() to see available nodes (case-sensitive)."

    # Check console type
    console_type = node['console_type']
    if console_type not in ['telnet']:
        return f"Console type '{console_type}' not supported (only 'telnet' currently supported). Check node configuration."

    if not node['console']:
        return f"Node '{node_name}' has no console configured. Verify node is started with list_nodes()."

    # Extract host from GNS3 client config
    host = app.gns3.base_url.split('//')[1].split(':')[0]
    port = node['console']

    # Connect
    try:
        await app.console.connect(host, port, node_name)
        return None
    except Exception as e:
        return f"Failed to connect: {str(e)}"


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

    # Process escape sequences unless raw mode
    if not raw:
        # First handle escape sequences (backslash-escaped strings)
        data = data.replace('\\r\\n', '\r\n')  # \r\n → CR+LF
        data = data.replace('\\n', '\n')       # \n → LF
        data = data.replace('\\r', '\r')       # \r → CR
        data = data.replace('\\t', '\t')       # \t → tab
        data = data.replace('\\x1b', '\x1b')   # \x1b → ESC

        # Then normalize all newlines to \r\n for console compatibility
        # This handles copy-pasted multi-line text
        data = data.replace('\r\n', '\n')      # Normalize CRLF to LF first
        data = data.replace('\r', '\n')        # Normalize CR to LF
        data = data.replace('\n', '\r\n')      # Convert all LF to CRLF

    success = await app.console.send_by_node(node_name, data)
    return "Sent successfully" if success else "Failed to send"


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
    context: int = 0
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
        return (f"Error: 'pages' parameter can only be used with mode='num_pages'.\n"
                f"Current mode: '{mode}', pages: {pages}\n"
                f"Either change mode to 'num_pages' or remove the 'pages' parameter.")

    # Validate mode parameter
    if mode not in ("diff", "last_page", "num_pages", "all"):
        return (f"Invalid mode '{mode}'. Valid modes:\n"
                f"  'diff' - New output since last read (default)\n"
                f"  'last_page' - Last ~25 lines\n"
                f"  'num_pages' - Last N pages (use 'pages' parameter)\n"
                f"  'all' - Entire buffer (WARNING: May be very large!)")

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
            output = '\n'.join(lines[-25:]) if len(lines) > 25 else full_output
        else:
            output = None
    elif mode == "num_pages":
        # Return last N pages (~25 lines per page)
        full_output = app.console.get_output_by_node(node_name)
        if full_output:
            lines = full_output.splitlines()
            lines_to_return = 25 * pages
            output = '\n'.join(lines[-lines_to_return:]) if len(lines) > lines_to_return else full_output
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
            context=context
        )

    return output if output is not None else "No output available"


def _grep_filter(
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


async def disconnect_console_impl(app: "AppContext", node_name: str) -> str:
    """Disconnect console session

    Args:
        node_name: Name of the node

    Returns:
        JSON with status
    """
    success = await app.console.disconnect_by_node(node_name)

    return json.dumps({
        "success": success,
        "node_name": node_name,
        "message": "Disconnected successfully" if success else "No active session for this node"
    }, indent=2)


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
            created_at=session_info.get("created_at")
        )
    else:
        status = ConsoleStatus(
            connected=False,
            node_name=node_name
        )

    return json.dumps(status.model_dump(), indent=2)


async def send_and_wait_console_impl(
    app: "AppContext",
    node_name: str,
    command: str,
    wait_pattern: Optional[str] = None,
    timeout: int = 30,
    raw: bool = False
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
        return json.dumps({
            "error": error,
            "output": "",
            "pattern_found": False,
            "timeout_occurred": False
        }, indent=2)

    # Process escape sequences unless raw mode
    if not raw:
        # First handle escape sequences (backslash-escaped strings)
        command = command.replace('\\r\\n', '\r\n')  # \r\n → CR+LF
        command = command.replace('\\n', '\n')       # \n → LF
        command = command.replace('\\r', '\r')       # \r → CR
        command = command.replace('\\t', '\t')       # \t → tab
        command = command.replace('\\x1b', '\x1b')   # \x1b → ESC

        # Then normalize all newlines to \r\n for console compatibility
        command = command.replace('\r\n', '\n')      # Normalize CRLF to LF first
        command = command.replace('\r', '\n')        # Normalize CR to LF
        command = command.replace('\n', '\r\n')      # Convert all LF to CRLF

    # Send command
    success = await app.console.send_by_node(node_name, command)
    if not success:
        return json.dumps({
            "error": "Failed to send command",
            "output": "",
            "pattern_found": False,
            "timeout_occurred": False
        }, indent=2)

    # Wait for pattern or timeout
    start_time = time.time()
    pattern_found = False
    timeout_occurred = False

    if wait_pattern:
        try:
            pattern_re = re.compile(wait_pattern)
        except re.error as e:
            return json.dumps({
                "error": f"Invalid regex pattern: {str(e)}",
                "output": "",
                "pattern_found": False,
                "timeout_occurred": False
            }, indent=2)

        # Poll console every 0.5s
        while (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)
            output = app.console.get_diff_by_node(node_name) or ""

            if pattern_re.search(output):
                pattern_found = True
                break

        if not pattern_found:
            timeout_occurred = True
    else:
        # No pattern - just wait 2 seconds
        await asyncio.sleep(2)

    wait_time = time.time() - start_time

    # Get all output since command was sent
    output = app.console.get_diff_by_node(node_name) or ""

    return json.dumps({
        "output": output,
        "pattern_found": pattern_found,
        "timeout_occurred": timeout_occurred,
        "wait_time": round(wait_time, 2)
    }, indent=2)


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

    # Map key names to escape sequences
    SPECIAL_KEYS = {
        # Navigation
        'up': '\x1b[A',
        'down': '\x1b[B',
        'right': '\x1b[C',
        'left': '\x1b[D',
        'home': '\x1b[H',
        'end': '\x1b[F',
        'pageup': '\x1b[5~',
        'pagedown': '\x1b[6~',

        # Editing
        'enter': '\r\n',
        'backspace': '\x7f',
        'delete': '\x1b[3~',
        'tab': '\t',
        'esc': '\x1b',

        # Control sequences
        'ctrl_c': '\x03',
        'ctrl_d': '\x04',
        'ctrl_z': '\x1a',
        'ctrl_a': '\x01',
        'ctrl_e': '\x05',

        # Function keys
        'f1': '\x1bOP',
        'f2': '\x1bOQ',
        'f3': '\x1bOR',
        'f4': '\x1bOS',
        'f5': '\x1b[15~',
        'f6': '\x1b[17~',
        'f7': '\x1b[18~',
        'f8': '\x1b[19~',
        'f9': '\x1b[20~',
        'f10': '\x1b[21~',
        'f11': '\x1b[23~',
        'f12': '\x1b[24~',
    }

    key_lower = key.lower()
    if key_lower not in SPECIAL_KEYS:
        return f"Unknown key: {key}. Supported keys: {', '.join(sorted(SPECIAL_KEYS.keys()))}"

    keystroke = SPECIAL_KEYS[key_lower]
    success = await app.console.send_by_node(node_name, keystroke)
    return "Sent successfully" if success else "Failed to send"
