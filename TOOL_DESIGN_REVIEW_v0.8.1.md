# GNS3 MCP Server Tool Review - Comprehensive Analysis

**Review Date:** 2025-01-24
**Current Version:** v0.8.1
**Reviewer:** mcp-server-architect agent
**Overall Grade:** B+ (would be A- after Priority 1-2 fixes)

---

## Executive Summary

The GNS3 MCP server (v0.8.1) provides 21 well-structured tools for network lab automation. Overall quality is **high**, with strong MCP compliance, consistent JSON returns, and type-safe Pydantic models. However, several areas need improvement for better usability, consistency, and documentation clarity.

**Current Version in Code:** v0.6.4 (main.py line 1)
**Current Version in Manifest:** v0.8.1 (manifest.json line 5)
**VERSION MISMATCH CRITICAL ISSUE** - These must be synchronized.

---

## Critical Issues (Priority 1)

### 1. VERSION SYNCHRONIZATION MISMATCH ⚠️
**Location:** `main.py` line 1 vs `manifest.json` line 5

**Problem:**
- Code header shows v0.6.4
- Manifest shows v0.8.1
- User instructions say v0.8.1 with v0.8.0 changes (read_console defaults, create_drawing)

**Impact:** Users may get confused about actual version and feature availability.

**Fix Required:**
```python
# main.py line 1 - UPDATE TO:
"""GNS3 MCP Server v0.8.1

Model Context Protocol server for GNS3 lab automation.
Provides tools for managing projects, nodes, links, console access, and drawings.

Version 0.8.1 - Enhanced Documentation:
- DOCS: Added best practice guidance for send_and_wait_console()
  * Check prompt first with read_console() before using wait patterns
  * Example workflow shows step-by-step prompt identification

Version 0.8.0 - Console and Drawing Redesign:
...
```

---

### 2. INCONSISTENT PARAMETER DESCRIPTIONS
**Locations:** Multiple tools

**Issues:**

**A. `force_refresh` parameter inconsistency**
- `list_projects()` line 439: "Force cache refresh (default: False)"
- `list_nodes()` line 534: "Force cache refresh (default: False)"
- `get_node_details()` line 597: "Force cache refresh (default: False)"
- `get_links()` line 671: "Force cache refresh (default: False)"

**Problem:** Description doesn't explain WHEN or WHY to use force_refresh.

**Better description:**
```python
force_refresh: Bypass cache and fetch fresh data from GNS3 API (default: False).
              Use when you need real-time state (after external changes to topology).
              Cache TTL: 30s for nodes/links, 60s for projects.
```

**B. `node_name` vs `project_name` naming inconsistency**
- Most tools use `node_name` (console tools, set_node, etc.)
- `open_project()` uses `project_name` (line 478)

**Issue:** Inconsistent naming convention for resource identifiers.

**Recommendation:** Standardize on `<resource>_name` pattern (already mostly followed).

---

### 3. MISSING PARAMETER VALIDATION IN TOOL DESCRIPTIONS

**Location:** `set_node()` line 784

**Current description:** Lists all parameters but doesn't explain validation rules or constraints.

**Problems:**
- Line 832: "Node must be stopped" for name changes - NOT in docstring
- Line 869: Port configuration only for ethernet switches - NOT in docstring
- Line 879: Hardware properties wrapped in 'properties' for QEMU - NOT in docstring

**Better docstring:**
```python
"""Configure node properties and/or control node state

Validation Rules:
- name: Can only be changed when node is stopped
- ports: Only supported for ethernet_switch node type
- Hardware properties (ram, cpus, hdd_disk_image, adapters):
  * Applied to QEMU nodes via nested 'properties' object
  * Other node types: merged directly into payload
- console_type: Changes console access method (telnet, vnc, spice, none)

Action Types:
- start: Start the node (async operation, may take 30-60s for boot)
- stop: Stop the node (async operation, waits for clean shutdown)
- suspend: Suspend node (VM only, faster than stop)
- reload: Reload node (equivalent to restart without retry logic)
- restart: Stop node with retry logic (3 attempts × 5s), then start
          Use for clean restarts when node needs confirmed stop

Args:
    node_name: Name of the node to modify
    action: Action to perform (start/stop/suspend/reload/restart)
    x: X coordinate (top-left corner of icon)
    y: Y coordinate (top-left corner of icon)
    z: Z-order/layer (0=background, higher=foreground)
    locked: Lock node position (prevents GUI drag)
    ports: Number of ports (ethernet_switch only, creates ports_mapping)
    name: New name (requires node stopped)
    ram: RAM in MB (QEMU nodes only)
    cpus: Number of CPUs (QEMU nodes only)
    hdd_disk_image: Path to HDD disk image (QEMU nodes only)
    adapters: Number of network adapters (QEMU nodes only)
    console_type: Console type (telnet, vnc, spice, none)

Returns:
    JSON with:
    {
        "message": "Node updated successfully",
        "changes": ["Started Router1", "Updated: x=100, y=200"]
    }

Example - Position and start:
    set_node("R1", action="start", x=100, y=200, z=1)

Example - Configure switch ports:
    set_node("Switch1", ports=16)  # ethernet_switch only

Example - Rename (requires stopped):
    set_node("R1", action="stop")
    await 5 seconds
    set_node("R1", name="Router-Core-1")
```

---

### 4. CONSOLE TOOL WORKFLOW CONFUSION

**Location:** Console tools (lines 1020-1642)

**Issues:**

**A. Timing guidance scattered across tools**
- `send_console()` line 1027: "Allow 0.5-2 seconds after send before reading"
- `read_console()` line 1097: "After send_console(): Wait 0.5-2s before reading"
- `send_and_wait_console()` line 1248: Has timing built-in

**Problem:** User must read 3 different docstrings to understand timing.

**B. `read_console()` parameter combinations confusing**
- `diff=True` (default since v0.8.0) - new output only
- `diff=False, last_page=True` - last 25 lines
- `diff=False, last_page=False` - full buffer

**Problem:** Parameter combinations not intuitive. Why not separate functions or clearer parameter names?

**Better design options:**

**Option 1: Separate functions (BREAKING)**
```python
read_console_new(node_name)  # Default behavior - new output
read_console_recent(node_name, lines=25)  # Last N lines
read_console_all(node_name)  # Full buffer
```

**Option 2: Clearer parameters (BACKWARD COMPATIBLE)**
```python
@mcp.tool()
async def read_console(ctx: Context,
                      node_name: str,
                      mode: str = "new") -> str:
    """Read console output (auto-connects if needed)

    Args:
        node_name: Name of the node
        mode: Output mode:
              "new" (default): Only new output since last read (diff mode)
              "recent": Last ~25 lines of buffer
              "all": Entire buffer since connection

    Returns:
        Console output or "No output available"

    Example - Default (new output only):
        output = read_console("R1")  # mode="new" by default

    Example - Check recent history:
        output = read_console("R1", mode="recent")  # Last 25 lines

    Example - Get everything:
        output = read_console("R1", mode="all")  # Full buffer
    """
```

---

### 5. ERROR RESPONSES LACK ACTIONABLE GUIDANCE

**Location:** Error handling throughout

**Examples:**

**A. `validate_current_project()` line 389**
```python
return json.dumps(ErrorResponse(
    error="No project opened",
    details="Use open_project() to open a project first"
).model_dump(), indent=2)
```

**Problem:** Tells user to call `open_project()` but doesn't show HOW to find project name.

**Better:**
```python
details="No project is currently open. First call list_projects() to see available projects, then call open_project(project_name) to open one."
```

**B. `get_node_details()` line 622**
```python
return json.dumps(ErrorResponse(
    error="Node not found",
    details=f"No node named '{node_name}' in current project. Use list_nodes() to see available nodes."
).model_dump(), indent=2)
```

**Good:** This one IS actionable! Use this pattern everywhere.

**C. `set_connection()` validation errors (lines 1688-1761)**

**Problem:** Error says "Validation failed at operation 0" but doesn't explain what the actual validation rules are.

**Better:** Include validation rule in error:
```python
details=f"Port R1 adapter 0 port 0 already connected to R2 adapter 0 port 1. First disconnect the existing link with set_connection([{{'action': 'disconnect', 'link_id': '{link_id}'}}])"
```

---

## Major Issues (Priority 2)

### 6. TOOL GROUPING IN MANIFEST NOT SEMANTIC

**Location:** `manifest.json` lines 59-143

**Current order:** Sequential (projects → nodes → links → console → drawings)

**Problem:** Related tools not grouped logically. For example:
- `set_connection` (line 113) separated from `get_links` (line 77)
- Console tools scattered (send, read, disconnect, status, send_and_wait, detect, keystroke)

**Better grouping:**
```json
"tools": [
  // Project Management
  {"name": "list_projects", "description": "..."},
  {"name": "open_project", "description": "..."},

  // Node Discovery & Control
  {"name": "list_nodes", "description": "..."},
  {"name": "get_node_details", "description": "..."},
  {"name": "set_node", "description": "..."},
  {"name": "delete_node", "description": "..."},
  {"name": "create_node", "description": "..."},
  {"name": "list_templates", "description": "..."},

  // Topology & Links
  {"name": "get_links", "description": "..."},
  {"name": "set_connection", "description": "..."},

  // Console Access (Interactive)
  {"name": "send_console", "description": "..."},
  {"name": "read_console", "description": "..."},
  {"name": "disconnect_console", "description": "..."},
  {"name": "get_console_status", "description": "..."},

  // Console Access (Automated)
  {"name": "send_and_wait_console", "description": "..."},
  {"name": "send_keystroke", "description": "..."},
  {"name": "detect_console_state", "description": "..."},

  // Drawings & Visualization
  {"name": "list_drawings", "description": "..."},
  {"name": "create_drawing", "description": "..."},
  {"name": "delete_drawing", "description": "..."},
  {"name": "export_topology_diagram", "description": "..."}
]
```

---

### 7. CONSOLE STATE DETECTION OVERENGINEERED

**Location:** `detect_console_state()` lines 1476-1642

**Issues:**

**A. Pattern library (DEVICE_PATTERNS) lines 98-139**
- Defines patterns for cisco_ios, mikrotik, juniper, arista, linux
- Detection logic only actually uses MikroTik-specific patterns (lines 1562-1584)
- Generic patterns used for everything else (lines 1587-1633)

**Problem:** 80% of pattern library is dead code.

**B. Confidence scoring (lines 1555-1556, 1593-1633)**
- Returns "high", "medium", or "low" confidence
- But confidence is subjective and not documented

**What does "high" vs "medium" mean? When should user trust output?**

**C. Multiple detection modes**
- Device-specific (only MikroTik actually implemented)
- Generic pattern matching (everyone else)
- Fallback states (booting, unknown)

**Better approach:**

**Option 1: Simplify to generic patterns only**
```python
# Remove device-specific detection (mostly unused)
# Keep only generic patterns that work for most devices
# Document which devices are known to work well
```

**Option 2: Complete device-specific implementation**
```python
# Implement all patterns in DEVICE_PATTERNS
# Test with actual devices
# Document detection accuracy per device
```

**Recommendation:** Option 1 - simplify. Current implementation promises device detection but only delivers for MikroTik.

---

### 8. DRAWING TOOLS - INCONSISTENT COORDINATE DOCUMENTATION

**Location:** `create_drawing()` lines 2014-2167

**Issue:** Parameter descriptions for coordinate meanings vary by drawing type:

- Rectangle: "x: X coordinate (start point for line, top-left for others)"
- Line: "x: X coordinate (start point for line, top-left for others)"
- Text: Same description
- Ellipse: Line 2058: "Note: Ellipse center will be at (x + rx, y + ry)"

**Problem:** Ellipse uses DIFFERENT coordinate interpretation (top-left of bounding box, not center).

**But note says center!** This is confusing.

**Clarification needed:**
```python
"""Create a drawing object (rectangle, ellipse, line, or text)

Coordinate System:
- Rectangle: (x, y) = top-left corner of rectangle
- Ellipse: (x, y) = top-left corner of bounding box
           Center of ellipse will be at (x + rx, y + ry)
- Line: (x, y) = start point, line extends to (x + x2, y + y2)
- Text: (x, y) = top-left corner of text bounding box

Args:
    drawing_type: Type of drawing - "rectangle", "ellipse", "line", or "text"
    x: X coordinate (see Coordinate System above)
    y: Y coordinate (see Coordinate System above)
    ...
```

---

### 9. `export_topology_diagram()` MISSING FEATURE DOCUMENTATION

**Location:** `export_topology_diagram()` lines 2197-end

**Current documentation:** Lines 2204-2226 explain coordinate system and parameters.

**Missing:**
1. What visual elements are included in export?
   - Nodes (yes, with status colors)
   - Links (yes, with port status indicators)
   - Labels (yes)
   - Drawings (yes)
   - **But this isn't documented in docstring!**

2. What are the status indicators?
   - Green/red on nodes? Ports? Links?
   - **Not explained in tool description**

3. Output format details
   - SVG vs PNG differences
   - Image resolution/DPI for PNG
   - **Not documented**

**Better docstring:**
```python
"""Export topology as SVG and/or PNG diagram

Creates a visual diagram of the current topology with all elements:
- Nodes: Rendered with actual GNS3 icons
  * Started nodes: Green border
  * Stopped nodes: Red border
  * Suspended nodes: Yellow border
- Links: Rendered as lines connecting node centers
  * Active ports: Green circles at connection points
  * Shutdown ports: Red circles at connection points
- Labels: Positioned exactly as in GNS3 GUI
- Drawings: All shapes, lines, and text rendered with proper z-order

Output Formats:
- SVG: Vector format, scales to any size, includes fonts
- PNG: Raster format, 96 DPI, requires Cairo library
- Both: Creates .svg and .png files with same base name

GNS3 Coordinate System:
...existing coordinate documentation...

Args:
    output_path: Base path for output files (without extension)
                 Example: "C:/output/topology" creates "topology.svg" and "topology.png"
    format: Output format - "svg", "png", or "both" (default: "both")
    crop_x: Optional crop X coordinate (default: auto-fit to content)
    crop_y: Optional crop Y coordinate (default: auto-fit to content)
    crop_width: Optional crop width (default: auto-fit to content)
    crop_height: Optional crop height (default: auto-fit to content)

Returns:
    JSON with:
    {
        "svg_path": "C:/output/topology.svg",  # or null if format != "svg" or "both"
        "png_path": "C:/output/topology.png",  # or null if format != "png" or "both"
        "width": 800,
        "height": 600,
        "node_count": 5,
        "link_count": 7,
        "drawing_count": 3
    }

Example - Export to PNG only:
    export_topology_diagram("C:/diagrams/lab", format="png")

Example - Export with custom crop:
    export_topology_diagram("C:/diagrams/lab", crop_x=0, crop_y=0,
                          crop_width=1000, crop_height=800)
```

---

## Medium Issues (Priority 3)

### 10. REDUNDANT ERROR HANDLING PATTERN

**Location:** Most tool functions

**Pattern repeated throughout:**
```python
except Exception as e:
    return json.dumps(ErrorResponse(
        error="Failed to <action>",
        details=str(e)
    ).model_dump(), indent=2)
```

**Issues:**

1. **Generic error messages** - "Failed to list nodes", "Failed to get links", etc.
2. **Raw exception strings exposed** - `str(e)` may leak implementation details
3. **No structured error codes** - Can't programmatically distinguish error types

**Better approach:**

**A. Add error categorization:**
```python
class ErrorCategory:
    NOT_FOUND = "not_found"
    VALIDATION = "validation_error"
    API_ERROR = "api_error"
    AUTH_ERROR = "authentication_error"
    TIMEOUT = "timeout_error"
```

**B. Enhanced ErrorResponse model:**
```python
class ErrorResponse(BaseModel):
    error: str  # Human-readable summary
    details: Optional[str] = None  # Detailed explanation
    error_code: Optional[str] = None  # Structured error code (NOT_FOUND, etc.)
    field: Optional[str] = None  # Field that caused error
    operation_index: Optional[int] = None  # For batch operations
    suggested_action: Optional[str] = None  # What user should do next
```

**C. Usage example:**
```python
if not node:
    return json.dumps(ErrorResponse(
        error="Node not found",
        error_code="NOT_FOUND",
        details=f"No node named '{node_name}' in current project",
        field="node_name",
        suggested_action="Call list_nodes() to see available nodes"
    ).model_dump(), indent=2)
```

---

### 11. INCONSISTENT RETURN VALUE STRUCTURES

**Location:** Throughout

**Examples:**

**A. Success messages vary:**
- `set_node()` line 976: `{"message": "...", "changes": [...]}`
- `delete_node()` line 1879: `{"message": "..."}`
- `create_node()` line 1966: `{"message": "...", "node": {...}}`
- `disconnect_console()` line 1168: `{"success": true, "node_name": "...", "message": "..."}`

**Problem:** No standard success response structure.

**Better: Standardize:**
```python
# All tool success responses follow this pattern:
{
    "success": true,  # Always present
    "message": "Human-readable summary",  # Always present
    "data": {...},  # Optional - actual result data
    "metadata": {...}  # Optional - supplementary info (timing, counts, etc.)
}
```

**B. List tools return arrays directly:**
- `list_projects()` line 468: Returns JSON array of ProjectInfo
- `list_nodes()` line 582: Returns JSON array of NodeInfo
- `get_links()` line 761: Returns `{"links": [...], "warnings": ...}`

**Inconsistency:** `get_links()` wraps in object with warnings, others return raw arrays.

**Better:** All list tools return structured response:
```python
{
    "items": [...],  # Always use "items" key
    "count": 5,
    "warnings": [...] or null
}
```

---

### 12. MISSING TOOL: `get_project_details()`

**Current:** `list_projects()` returns all projects, `open_project()` opens and returns one.

**Gap:** No way to get details of a SPECIFIC project without opening it or listing all.

**Use case:** User wants to check if project is already opened, or inspect project properties without opening.

**Proposed tool:**
```python
@mcp.tool()
async def get_project_details(ctx: Context, project_name: str,
                              force_refresh: bool = False) -> str:
    """Get detailed information about a specific project

    Args:
        project_name: Name of the project
        force_refresh: Bypass cache (default: False)

    Returns:
        JSON with ProjectInfo or error if not found

    Example:
        details = get_project_details("Lab-OSPF")
        if details["status"] == "opened":
            print("Project already open")
    """
```

---

### 13. CACHE VISIBILITY & CONTROL LACKING

**Location:** Cache usage throughout, DataCache class in cache.py

**Issues:**

1. **force_refresh parameter inconsistently available**
   - Available on: list_projects, list_nodes, get_node_details, get_links
   - NOT available on: Most other tools that use cache indirectly

2. **No tool to inspect cache state**
   - Cache stats logged on shutdown (line 372)
   - But no way for user to check cache status or force global cache clear

3. **Cache TTL not exposed to users**
   - Hardcoded: 30s for nodes/links, 60s for projects (line 334)
   - User can't see when cache will expire

**Proposed enhancement:**
```python
@mcp.tool()
async def get_cache_stats(ctx: Context) -> str:
    """Get cache statistics and TTL information

    Returns:
        JSON with:
        {
            "projects": {"hits": 10, "misses": 2, "ttl_seconds": 60},
            "nodes": {"hits": 50, "misses": 5, "ttl_seconds": 30, "per_project": {...}},
            "links": {"hits": 40, "misses": 3, "ttl_seconds": 30, "per_project": {...}}
        }
    """

@mcp.tool()
async def clear_cache(ctx: Context, cache_type: Optional[str] = None) -> str:
    """Clear MCP server cache

    Args:
        cache_type: Type to clear - "all", "projects", "nodes", "links", or null for all

    Returns:
        JSON confirmation

    Use when external changes to GNS3 (via GUI) need immediate reflection
    """
```

---

## Minor Issues (Priority 4)

### 14. DOCSTRING FORMATTING INCONSISTENCIES

**Issues:**

**A. Some tools have "BEST PRACTICE" sections, others don't**
- `send_and_wait_console()` line 1252: Has "BEST PRACTICE" section (v0.8.1)
- `read_console()` line 1105: Has "State Detection Tips" section
- Other console tools: No best practice sections

**Recommendation:** Either add best practices to all tools or remove from some for consistency.

**B. Example sections vary in format**
- Some use "Example - ..." format
- Some use "Example: ..." format
- Some have multiple examples, some none

**Standardize:**
```python
Examples:
    # Example 1: Basic usage
    result = tool_name(param1, param2)

    # Example 2: Advanced usage
    result = tool_name(param1, param2, optional_param="value")
```

---

### 15. NO TOOL FOR BULK NODE OPERATIONS

**Gap:** User must call `set_node()` in loop for multiple nodes.

**Use case:** Start all routers in project, stop all nodes, set positions for multiple nodes.

**Proposed tool:**
```python
@mcp.tool()
async def bulk_set_nodes(ctx: Context, operations: List[Dict[str, Any]]) -> str:
    """Batch node operations with validation

    Similar to set_connection() but for node operations.

    Args:
        operations: List of set_node operations:
            {
                "node_name": "Router1",
                "action": "start",  # optional
                "x": 100,  # optional
                "y": 200,  # optional
                ...
            }

    Returns:
        JSON with OperationResult (completed and failed)

    Example - Start multiple nodes:
        bulk_set_nodes([
            {"node_name": "R1", "action": "start"},
            {"node_name": "R2", "action": "start"},
            {"node_name": "SW1", "action": "start"}
        ])
    """
```

---

### 16. `send_keystroke()` KEY LIST NOT EXHAUSTIVE

**Location:** `send_keystroke()` lines 1426-1465

**Current keys:** up, down, left, right, home, end, pageup, pagedown, enter, backspace, delete, tab, esc, ctrl_c/d/z/a/e, f1-f12

**Missing common keys:**
- Insert
- Shift+Tab (reverse tab)
- Ctrl+K, Ctrl+U, Ctrl+W (common Unix shortcuts)
- Alt sequences (Alt+B, Alt+F for word navigation)

**Recommendation:** Add to docstring that only listed keys are supported, and provide method for users to request additions.

---

## Design Improvements (Priority 5)

### 17. CONSIDER TOOL ANNOTATIONS

**Current:** No MCP tool annotations used.

**MCP specification supports annotations:**
- `readOnly` - Tool doesn't modify state
- `destructive` - Tool deletes/destroys resources
- `idempotent` - Multiple calls with same params produce same result
- `openWorld` - Tool may have side effects beyond stated behavior

**Benefit:** Claude can make better decisions about tool usage.

**Proposed annotations:**

```python
# Read-only tools
@mcp.tool(annotations={"readOnly": True})
async def list_projects(...): ...

@mcp.tool(annotations={"readOnly": True})
async def list_nodes(...): ...

@mcp.tool(annotations={"readOnly": True})
async def get_links(...): ...

# Destructive tools
@mcp.tool(annotations={"destructive": True})
async def delete_node(...): ...

@mcp.tool(annotations={"destructive": True})
async def delete_drawing(...): ...

# Idempotent tools
@mcp.tool(annotations={"idempotent": True})
async def open_project(...): ...  # Opening already-open project is safe

# Complex tools
@mcp.tool(annotations={"openWorld": True})
async def set_connection(...): ...  # Modifies topology state
```

---

### 18. NO SUPPORT FOR ASYNC OPERATION POLLING

**Issue:** Some GNS3 operations are asynchronous (node start/stop).

**Current approach:**
- `set_node()` with `action="start"` returns immediately
- `set_node()` with `action="restart"` polls 3×5s (line 943-951)

**Gap:** No general-purpose way to wait for node state.

**Proposed enhancement:**
```python
@mcp.tool()
async def wait_for_node_state(ctx: Context, node_name: str,
                              desired_state: str,
                              timeout: int = 60,
                              poll_interval: int = 5) -> str:
    """Wait for node to reach desired state

    Polls node status until desired state reached or timeout.

    Args:
        node_name: Name of the node
        desired_state: State to wait for ("started", "stopped", "suspended")
        timeout: Maximum wait time in seconds (default: 60)
        poll_interval: Polling interval in seconds (default: 5)

    Returns:
        JSON with:
        {
            "success": true,
            "final_state": "started",
            "wait_time": 12.5,
            "timeout_occurred": false
        }

    Example - Wait for node to start:
        set_node("R1", action="start")
        result = wait_for_node_state("R1", "started", timeout=60)
        if result["success"]:
            print("Node started successfully")
    """
```

---

## Documentation Improvements

### 19. SKILL.MD VS TOOL DOCSTRINGS DRIFT

**Issue:** Information in SKILL.md may not match current tool behavior.

**Example:** SKILL.md lines 91-93 say `read_console()` defaults to diff=True (correct for v0.8.0), but doesn't explain `last_page` parameter.

**Recommendation:**
1. Add note at top of SKILL.md: "For authoritative parameter documentation, see tool docstrings. This guide focuses on workflows."
2. Regular audits to ensure examples in SKILL.md match current tool API.

---

### 20. NO TROUBLESHOOTING GUIDE IN TOOL RESPONSES

**Issue:** When tools fail, error messages don't point to troubleshooting resources.

**Proposed:** Add optional `troubleshooting_url` field to ErrorResponse:

```python
class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    error_code: Optional[str] = None
    suggested_action: Optional[str] = None
    troubleshooting_url: Optional[str] = None  # NEW
```

**Usage:**
```python
return json.dumps(ErrorResponse(
    error="Console connection failed",
    details="Telnet connection to 192.168.1.20:5000 timed out",
    error_code="CONNECTION_TIMEOUT",
    suggested_action="Verify node is started and console type is 'telnet'",
    troubleshooting_url="https://github.com/user/gns3-mcp/blob/master/docs/console-troubleshooting.md"
).model_dump(), indent=2)
```

---

## Summary of Recommendations

### Immediate Actions (v0.8.2 - Bugfix Release)

1. **Fix version mismatch** - Sync main.py header to v0.8.1
2. **Enhance error messages** - Add suggested_action to all error responses
3. **Document set_node() validation rules** - Add to docstring
4. **Clarify read_console() modes** - Consider mode="new"/"recent"/"all" parameter

### Next Minor Release (v0.9.0 - Enhancement)

5. **Simplify detect_console_state()** - Remove unused device patterns
6. **Standardize return value structures** - All tools use {success, message, data}
7. **Add tool annotations** - readOnly, destructive, idempotent
8. **Group tools in manifest semantically** - Project/Node/Console/Drawing sections

### Future Major Release (v1.0.0 - Breaking Changes)

9. **Redesign read_console()** - Use mode parameter instead of diff+last_page
10. **Add missing tools** - get_project_details, get_cache_stats, clear_cache, bulk_set_nodes, wait_for_node_state
11. **Enhanced error handling** - Error codes, categories, structured responses

---

## MCP Protocol Compliance

### ✅ Strengths

1. **JSON-RPC 2.0 over stdio** - Correctly implemented (FastMCP handles this)
2. **Type-safe data models** - Pydantic v2 used throughout
3. **JSON return values** - All tools return valid JSON strings
4. **Async/await patterns** - Proper non-blocking I/O
5. **Resource management** - Proper cleanup in lifespan context
6. **Session management** - Console sessions with proper lifecycle

### ⚠️ Areas for Improvement

1. **No tool annotations** - Could leverage MCP annotations for better UX
2. **No completions support** - Could provide argument suggestions (adapters, node names, etc.)
3. **No batching** - Could support batch operations for performance
4. **No progress indicators** - Long operations (node start, exports) have no progress callbacks

---

## Priority Ranking

**Must Fix (v0.8.2 - Bugfix):**
1. Version synchronization (Critical)
2. set_node() validation documentation (Major usability)
3. Error message improvements (Major usability)

**Should Fix (v0.9.0 - Minor Release):**
4. Console tool workflow clarification
5. detect_console_state() simplification
6. Return value standardization
7. Tool grouping in manifest

**Nice to Have (v1.0.0 - Major Release):**
8. read_console() redesign
9. Additional tools (get_project_details, cache control, bulk operations)
10. Tool annotations
11. Enhanced error handling with codes

---

## Files Requiring Changes

**Immediate (v0.8.2):**
- `mcp-server/server/main.py` - Version header, docstring improvements, error messages
- `skill/SKILL.md` - Sync with v0.8.1 changes

**Next Release (v0.9.0):**
- `mcp-server/server/main.py` - Return value standardization, annotations
- `mcp-server/server/models.py` - Enhanced ErrorResponse model
- `mcp-server/manifest.json` - Tool grouping reorganization

**Future (v1.0.0):**
- `mcp-server/server/main.py` - API redesigns, new tools
- `mcp-server/server/models.py` - Error code enums
- `skill/SKILL.md` - Major workflow updates

---

## Conclusion

The GNS3 MCP server is well-architected with strong fundamentals. The main issues are **documentation clarity**, **consistency**, and **user guidance**. No major architectural changes needed - mostly refinement and polish.

**Overall Grade: B+** (would be A- after fixing Priority 1-2 issues)
