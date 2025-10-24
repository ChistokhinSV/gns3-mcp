# GNS3 MCP Server - Project Instructions

Project-specific instructions for working with the GNS3 MCP server codebase.

## Project Overview

MCP server providing programmatic access to GNS3 network simulation labs. Includes:
- Desktop extension (.mcpb) for Claude Desktop
- Agent skill with GNS3 procedural knowledge
- Console management for device interaction
- GNS3 v3 API client with JWT authentication

## Current Version: v0.8.1

**Latest Release:** v0.8.1 - Documentation Enhancement (Patch)
- **ENHANCED**: Added best practice guidance for `send_and_wait_console()`
  - Tool docstring now includes prominent "BEST PRACTICE" section
  - Recommends checking prompt first with `read_console()` before using wait patterns
  - Added example showing recommended workflow: check prompt → use in automation
  - TIP added to `wait_pattern` parameter documentation
- **SKILL.md**: New section "Using send_and_wait_console for Automation"
  - 3-step workflow guide with examples
  - Comparison: when to use send_and_wait vs send+read
  - Best practices for avoiding common issues (wrong prompts, timeouts, missed output)
- **Files changed**:
  - `main.py`: Enhanced `send_and_wait_console()` docstring (lines 1247-1307)
  - `SKILL.md`: Added automation section and best practices (lines 139-184)
  - `manifest.json`: Updated to v0.8.1
- **Rationale**: Prevents common user errors from incorrect prompt patterns

**Previous:** v0.8.0 - Tool Redesign (Breaking Changes)
- **BREAKING**: `read_console()` now defaults to `diff=True` (was `diff=False`)
  - Previous: `read_console(node)` returned full buffer
  - Now: `read_console(node)` returns only new output since last read
  - Migration: Use `read_console(node, diff=False, last_page=False)` for old behavior
- **NEW**: `read_console()` added `last_page=True` parameter for last ~25 lines
  - `read_console(node)` - new output only (diff mode, default)
  - `read_console(node, diff=False, last_page=True)` - last ~25 lines
  - `read_console(node, diff=False, last_page=False)` - full buffer
- **BREAKING**: Removed individual drawing tools: `create_rectangle()`, `create_text()`, `create_ellipse()`
- **NEW**: Unified `create_drawing(drawing_type, ...)` tool
  - Supports `drawing_type`: "rectangle", "ellipse", "line", "text"
  - **Rectangle**: `create_drawing("rectangle", x, y, width=W, height=H, fill_color, border_color)`
  - **Ellipse**: `create_drawing("ellipse", x, y, rx=R1, ry=R2, fill_color, border_color)`
  - **Line**: `create_drawing("line", x, y, x2=X, y2=Y, border_color, border_width)` - NEW type
  - **Text**: `create_drawing("text", x, y, text=T, font_size, color, font_weight)`
- **Files changed**:
  - `main.py`: Modified `read_console()` defaults (line 1055), added unified `create_drawing()` (lines 2003-2136)
  - `main.py`: Added `create_line_svg()` helper function (lines 258-283)
  - `main.py`: Removed `create_rectangle()`, `create_text()`, `create_ellipse()` tools
  - `manifest.json`: Updated tool definitions for v0.8.0
  - `SKILL.md`: Updated documentation with new tool interfaces
- **Rationale**: Diff mode is most common use case for interactive sessions; unified drawing tool reduces API surface

**Previous:** v0.7.0 - Adapter Name Support (Feature)
- **NEW**: `set_connection()` now accepts adapter names in addition to numeric indexes
- **Adapter names**: Use port names like "eth0", "GigabitEthernet0/0", "Ethernet0" for better readability
- **Backward compatible**: Numeric adapter indexes still work (0, 1, 2, ...)
- **Enhanced responses**: Include both human-readable port names AND adapter/port numbers
- **Example**: `"adapter_a": 0, "port_a_name": "eth0"` in confirmation
- **Files changed**:
  - `link_validator.py`: Added `resolve_adapter_identifier()` method with port name mapping
  - `models.py`: Updated `ConnectOperation` to accept `Union[str, int]` for adapters
  - `main.py`: Resolution and validation logic for adapter names
  - `SKILL.md`: Updated documentation with adapter name examples
- **Use case**: More intuitive link creation - `adapter_a: "eth0"` instead of `adapter_a: 0`

**Previous:** v0.6.5 - Empty Response Handling (Bugfix)
- **Fixed node actions**: `start_node()`, `stop_node()`, `suspend_node()`, `reload_node()` now handle empty API responses
- **Issue**: GNS3 API returns HTTP 204 No Content (empty body) for these actions
- **Error**: Previously failed with "Expecting value: line 1 column 1 (char 0)" JSON parse error
- **Fix**: Check response status code and content before parsing JSON, return empty dict for 204/empty responses
- **Impact**: All node control actions now work correctly
- **Files changed**: `mcp-server/server/gns3_client.py` lines 112-162

**Previous:** v0.6.4 - Z-order Rendering Fix (Bugfix)
- **Fixed z-order**: Links render below nodes (z=min(nodes)-0.5), drawings/nodes intermixed by z-value
- **Painter's algorithm**: Ensures correct layering for overlapping elements

**Previous:** v0.6.3 - Font Fallback Chain (Bugfix)
- **Fixed font rendering**: Added CSS-style font fallback chains for consistent cross-platform SVG/PNG export
- **TypeWriter fallback**: TypeWriter → Courier New → Courier → Liberation Mono → Consolas → monospace
- **Display font fallback**: Gerbera Black/decorative → Georgia → Times New Roman → serif
- **Implementation**: `add_font_fallbacks()` helper function processes SVG style strings
- **Applied to**: Node labels and drawing text elements
- **Why needed**: Qt (GNS3 GUI) auto-resolves "TypeWriter" to system monospace, but SVG renderers need explicit fallbacks

**Previous:** v0.6.2 - Label Rendering Fix (Bugfix)
- **Fixed label positioning**: `export_topology_diagram()` now matches official GNS3 GUI rendering
- **Auto-centering**: Labels with x=None properly center above nodes (y=-25)
- **Dynamic text-anchor**: Text alignment (start/middle/end) based on label position
- **No offset additions**: Uses GNS3-stored positions directly, no incorrect calculations
- See [Label Rendering Implementation](#label-rendering-implementation-v062) section for details

**Previous:** v0.6.1 - Newline Normalization & Special Keystrokes
- **FIXED**: All newlines automatically converted to \r\n (CR+LF) for console compatibility
  - Copy-paste multi-line text directly - newlines just work
  - `send_console()` and `send_and_wait_console()` normalize all line endings (\n, \r, \r\n → \r\n)
  - Add `raw=True` parameter to disable processing
- **NEW**: `send_keystroke()` - Send special keys for TUI navigation and vim editing
  - Navigation: up, down, left, right, home, end, pageup, pagedown
  - Editing: enter (sends \r\n), backspace, delete, tab, esc
  - Control: ctrl_c, ctrl_d, ctrl_z, ctrl_a, ctrl_e
  - Function keys: f1-f12
- **FIXED**: `detect_console_state()` now checks only last non-empty line (not 5 lines)
  - Prevents detecting old prompts instead of current state
  - Fixed MikroTik password patterns: "new password>" not "new password:"

**Previous:** v0.6.0 - Interactive Console Tools
- **NEW**: `send_and_wait_console()` - Send command and wait for prompt pattern
  - Regex pattern matching with 0.5s polling interval
  - Timeout support for reliable automation
- **NEW**: `detect_console_state()` - Auto-detect device type and console state
  - Detects: Cisco IOS, MikroTik, Juniper, Arista, Linux
  - Identifies 9 console states with confidence scoring
- **ENHANCED**: Console tool docstrings with timing guidance
- Added DEVICE_PATTERNS library for auto-detection

**Previous:** v0.5.1 - Label Alignment
- Fixed node label alignment - right-aligned and vertically centered
- Note: v0.6.2 supersedes this with accurate GNS3-matching positioning

**Previous:** v0.5.0 - Port Status Indicators
- Topology export shows port status indicators
  - Green = port active (node started, link not suspended)
  - Red = port stopped (node stopped or link suspended)
- Enhanced `export_topology_diagram()` with visual status

**Previous:** v0.4.2 - Topology Export
- **NEW**: `export_topology_diagram()` - Export topology as SVG/PNG
- Renders nodes, links, and drawings
- Auto-fits to content with padding
- Supports custom crop regions

**Previous:** v0.4.0 - Node Creation & Drawing Objects
- **NEW**: `delete_node` - Remove nodes from projects
- **NEW**: `list_templates` - List available GNS3 templates
- **NEW**: `create_node` - Create nodes from templates at specified coordinates
- **NEW**: `list_drawings` - List drawing objects in project
- **NEW**: `create_rectangle` - Create colored rectangle drawings
- **NEW**: `create_text` - Create text labels with formatting
- **NEW**: `create_ellipse` - Create ellipse/circle drawings

**Previous:** v0.3.0 - Major Refactoring (Breaking Changes)
- **Type-safe operations**: Pydantic v2 models for all data structures
- **Two-phase validation**: Prevents partial topology changes in `set_connection()`
- **Performance caching**: 10× faster with TTL-based cache (30s for nodes/links, 60s for projects)
- **Multi-adapter support**: `set_connection()` now requires `adapter_a`/`adapter_b` parameters
- **JSON outputs**: All tools return structured JSON instead of formatted strings
- **New tool**: `get_console_status()` for checking console connection state
- **Better errors**: Detailed validation messages with suggested fixes
- See [MIGRATION_v0.3.md](MIGRATION_v0.3.md) for complete migration guide

**Previous:** v0.2.1 - Link Discovery
- Added `get_links()` tool for topology discovery
- Enhanced `set_connection()` with workflow guidance

**Previous:** v0.2.0 - Auto-Connect & Unified Control
- Console tools now use `node_name` instead of `session_id` (auto-connect)
- `start_node` + `stop_node` → unified `set_node` tool
- Added `set_connection` tool for link management

## Version Management

**CRITICAL**: Update extension version every time a change is made.

- **Bugfix**: Increment patch version (0.1.1 → 0.1.2)
- **New feature**: Increment minor version (0.1.2 → 0.2.0)
- **Breaking change**: Increment major version (0.2.0 → 1.0.0)

**Version Synchronization:**
- Server code and desktop extension (.mcpb) must have the **same version**
- Desktop extension is **automatically rebuilt** by git pre-commit hook
- If versions mismatch, Claude Desktop may use outdated code

**Steps to update version:**
1. Edit `mcp-server/manifest.json` - update `"version"` field
2. Commit your changes - pre-commit hook automatically rebuilds .mcpb
3. Verify version in build output: `gns3-mcp@X.Y.Z`
4. Reinstall in Claude Desktop (double-click .mcpb)

**Pre-commit Hook:**
- Located at `.git/hooks/pre-commit` (and `.bat` for Windows)
- Automatically detects changes to `mcp-server/server/` or `manifest.json`
- Rebuilds desktop extension and adds to commit
- Aborts commit if build fails

## File Structure

```
008. GNS3 MCP/
├── mcp-server/
│   ├── server/
│   │   ├── main.py              # FastMCP server (11 tools)
│   │   ├── gns3_client.py       # GNS3 v3 API client
│   │   ├── console_manager.py   # Telnet console manager
│   │   ├── models.py            # [v0.3.0] Pydantic data models
│   │   ├── link_validator.py    # [v0.3.0] Two-phase link validation
│   │   └── cache.py             # [v0.3.0] TTL-based data caching
│   ├── lib/                     # Bundled Python dependencies
│   ├── manifest.json            # Desktop extension manifest
│   ├── start_mcp.py            # Wrapper script for .env loading
│   └── mcp-server.mcpb          # Packaged extension
├── skill/
│   ├── SKILL.md                 # Agent skill documentation
│   └── examples/                # GNS3 workflow examples
├── tests/
│   ├── test_mcp_console.py      # Console manager tests
│   ├── interactive_console_test.py
│   ├── list_nodes_helper.py     # Node discovery helper
│   └── TEST_RESULTS.md          # Latest test results
├── .env                         # GNS3 credentials (gitignored)
├── .mcp.json                    # MCP server config (Claude Code)
├── requirements.txt             # Python dependencies
├── MIGRATION_v0.3.md           # [v0.3.0] Migration guide
├── REFACTORING_STATUS_v0.3.md  # [v0.3.0] Refactoring documentation
└── README.md                    # User documentation
```

## Development Workflow

### 1. Making Code Changes

**Before editing server code:**
```bash
# Read the current implementation
cat mcp-server/server/main.py
cat mcp-server/server/gns3_client.py
cat mcp-server/server/console_manager.py

# [v0.3.0] Architecture files
cat mcp-server/server/models.py        # Pydantic data models
cat mcp-server/server/link_validator.py  # Two-phase validation
cat mcp-server/server/cache.py         # TTL-based caching
```

**After editing:**
1. Test locally first (see Testing section)
2. Update version in manifest.json (increment appropriately)
3. Commit changes - pre-commit hook automatically rebuilds extension
4. Verify version in hook output: `gns3-mcp@X.Y.Z`
5. Reinstall and test in Claude Desktop (double-click .mcpb)

### 2. Testing

**Always test changes before packaging:**

```bash
# Test node discovery
python tests/list_nodes_helper.py

# Test console directly (verify telnet works)
python tests/interactive_console_test.py --port <PORT>

# Test ConsoleManager
python tests/test_mcp_console.py --port <PORT>

# Manual MCP server test
cd mcp-server
mcp dev server/main.py --host 192.168.1.20 --port 80 --username admin --password <PASS>
```

**Test device:** AlpineLinuxTest-1 (port 5014)
- Fast boot, simple login
- Good for automated testing
- See `tests/ALPINE_SETUP_GUIDE.md`

### 3. Packaging

**After any server code change:**

```bash
cd mcp-server
npx @anthropic-ai/mcpb pack

# Output: mcp-server.mcpb (~19MB)
```

**Validate manifest before packaging:**
```bash
npx @anthropic-ai/mcpb validate manifest.json
```

### 4. Installation

#### Claude Desktop

**To install/update in Claude Desktop:**
1. Close Claude Desktop completely
2. Double-click `mcp-server.mcpb`
3. Restart Claude Desktop
4. Check logs: `C:\Users\mail4\AppData\Roaming\Claude\logs\mcp-server-GNS3 Lab Controller.log`

#### Claude Code

**Project-scoped installation (recommended):**

Configuration files:
- `.mcp.json` - MCP server configuration (committed to git)
- `.env` - Credentials (gitignored)
- `mcp-server/start_mcp.py` - Wrapper script that loads .env

The wrapper script automatically:
1. Loads environment variables from `.env`
2. Adds `mcp-server/lib` and `mcp-server/server` to Python path
3. Starts the MCP server with credentials from environment

**Verify installation:**
```bash
claude mcp get gns3-lab
# Should show: Status: ✓ Connected
```

**Important:** MCP tools load at conversation start. After configuring the server, start a new conversation to access the tools.

**Global installation (optional):**
```powershell
claude mcp add --transport stdio gns3-lab --scope user -- `
  python "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-server\start_mcp.py"
```

**Key differences:**
- Claude Desktop: `.mcpb` package (user-wide), manual credential config
- Claude Code: `.mcp.json` + wrapper script (project-scoped), auto-loads .env
- Both use same Python server code

## Common Tasks

### Add New MCP Tool

1. Edit `mcp-server/server/main.py`
2. Add function decorated with `@mcp.tool()`:
   ```python
   @mcp.tool()
   async def new_tool(ctx: Context, param: str) -> str:
       """Tool description"""
       # Implementation
       return "result"
   ```
3. Update version in manifest.json
4. Test with `mcp dev`
5. Package and install

### Modify GNS3 API Client

1. Edit `mcp-server/server/gns3_client.py`
2. Refer to `data/SESSION.txt` for API endpoints
3. Use `httpx` async client
4. Return parsed JSON, not raw responses
5. Test changes before packaging

### Update Console Manager

1. Edit `mcp-server/server/console_manager.py`
2. Use telnetlib3 for connections
3. Keep background reader async task pattern
4. Test with `tests/test_mcp_console.py`
5. Verify buffer management and timeouts

### Update Agent Skill

1. Edit `skill/SKILL.md`
2. Follow progressive disclosure structure
3. Add device-specific commands if needed
4. Include examples for common workflows
5. No packaging needed (skill is separate)

## Dependency Management

**Python dependencies** (requirements.txt):
- `mcp>=1.2.1` - MCP protocol
- `httpx>=0.28.1` - HTTP client
- `telnetlib3>=2.0.4` - Telnet client
- `pydantic>=2.0.0` - Type-safe data models [v0.3.0]
- `python-dotenv>=1.1.1` - Environment variables

**Bundled dependencies** (mcp-server/lib/):
- Automatically bundled during packaging
- Do NOT commit lib/ folder to git
- Generated by: `pip install --target=lib -r requirements.txt`

**Update dependencies:**
```bash
# Update requirements.txt with new versions
pip install <package>==<version>

# Rebuild lib folder (if needed)
cd mcp-server
pip install --target=lib mcp httpx telnetlib3 pydantic python-dotenv
```

## Environment Variables

**Development** (.env file):
```
USER=admin
PASSWORD=<your-gns3-password>
GNS3_HOST=192.168.1.20
GNS3_PORT=80
```

**Production** (Claude Desktop):
- Configured via extension manifest
- User provides in Claude Desktop settings
- See manifest.json `user_config` section

## Troubleshooting

### Extension Won't Load in Claude Desktop

1. Check logs: `C:\Users\mail4\AppData\Roaming\Claude\logs\`
2. Validate manifest: `npx @anthropic-ai/mcpb validate manifest.json`
3. Verify PYTHONPATH in manifest includes lib/ and server/
4. Check Python dependencies are bundled in lib/

### Console Connection Fails

1. Test direct telnet: `python tests/interactive_console_test.py --port <PORT>`
2. Verify node is started in GNS3
3. Check console type is `telnet` (not vnc, spice, etc.)
4. Wait 5-10 seconds after node start before connecting
5. Review console_manager.py logs

### Authentication Fails

1. Verify credentials in .env
2. Test with curl:
   ```bash
   curl -X POST http://192.168.1.20/v3/access/users/authenticate \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"YOUR_PASSWORD"}'
   ```
3. Check GNS3 server is running
4. Verify GNS3 v3 API is enabled

### ModuleNotFoundError

1. Check lib/ folder exists and contains dependencies
2. Verify PYTHONPATH in manifest.json
3. Repackage extension: `npx @anthropic-ai/mcpb pack`
4. Use semicolon (;) separator on Windows, not colon (:)

## Code Conventions

### Logging

Use Python logging module with timestamp format:
```python
import logging

logger = logging.getLogger(__name__)
# Format: [HH:MM:SS DD.MM.YYYY] message
```

### Error Handling

- Always catch and log exceptions
- Return descriptive error messages to user
- Don't expose sensitive data in errors
- Use try/except in all async functions

### Async Patterns

- Use `async def` for I/O operations
- Use `await` for async calls
- Use `asyncio.create_task()` for background tasks
- Clean up tasks on disconnect

### Type Hints

Use type hints for function parameters and returns:
```python
async def connect(self, host: str, port: int) -> str:
    """Type hints help with IDE support"""
    pass
```

## v0.3.0 Architecture

### Pydantic Models (models.py)

All data structures use Pydantic v2 BaseModel for:
- Type validation at runtime
- JSON schema generation
- Clear error messages
- IDE autocomplete support

Example:
```python
from models import ConnectOperation, LinkInfo

# Validate connection operation
op = ConnectOperation(
    action="connect",
    node_a="R1",
    node_b="R2",
    port_a=0,
    port_b=0,
    adapter_a=0,  # Required in v0.3.0
    adapter_b=0
)

# Access validated fields
print(op.node_a)  # Type-safe
```

### Two-Phase Validation (link_validator.py)

LinkValidator prevents partial topology changes:

**Phase 1: Validation**
- Check all nodes exist
- Verify ports are available
- Validate adapters exist on devices
- Build simulated state (no API calls)

**Phase 2: Execution**
- Only execute if ALL operations valid
- Cache invalidation after success
- Atomic topology changes

Example workflow:
```python
validator = LinkValidator(nodes, links)

# Validate ALL operations first
for op in operations:
    error = validator.validate_connect(...)
    if error:
        return error_response  # STOP - no changes made

# All valid - execute ALL operations
for op in operations:
    await gns3.create_link(...)  # Safe - validated
```

### TTL-Based Caching (cache.py)

DataCache reduces API calls:
- 30s TTL for nodes and links
- 60s TTL for projects
- Automatic invalidation after mutations
- 10× performance improvement for batch operations

Example:
```python
# First call - cache miss (API call)
nodes = await cache.get_nodes(project_id, fetch_fn)

# Second call within 30s - cache hit (instant)
nodes = await cache.get_nodes(project_id, fetch_fn)

# Force refresh (bypass cache)
nodes = await cache.get_nodes(project_id, fetch_fn, force_refresh=True)

# Invalidate after mutations
await cache.invalidate_nodes(project_id)
```

### JSON Output Format

All tools return JSON for structured parsing:

```python
# Tool returns JSON string
result = await list_nodes()

# Parse in Python
import json
nodes = json.loads(result)
for node in nodes:
    print(node['name'], node['status'])

# Error responses are also JSON
{
    "error": "Validation failed at operation 0",
    "details": "Port R1 adapter 0 port 0 already connected...",
    "operation_index": 0
}
```

## Label Rendering Implementation (v0.6.2)

### Overview

The `export_topology_diagram()` tool creates SVG/PNG diagrams that visually match the official GNS3 GUI rendering. Version 0.6.2 fixed label positioning to accurately replicate GNS3's label behavior.

### GNS3 Label Coordinate System

**Official GNS3 Behavior** (from `gns3-gui/gns3/items/node_item.py`):

```python
# GNS3 stores labels with these properties:
label = {
    "text": "NodeName",           # Label text
    "x": 10,                      # X offset from node top-left (or None for auto-center)
    "y": -25,                     # Y offset from node top-left (typically -25 for above node)
    "rotation": 0,                # Rotation angle in degrees
    "style": "font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;"
}
```

**Key Concepts:**
1. **Node coordinates**: Top-left corner of icon (x, y)
2. **Icon sizes**: PNG images = 78×78, SVG icons = 58×58
3. **Label position**: Offset from node top-left corner
4. **Auto-centering**: When `x` is `None`, GNS3 centers label above node

### Label Positioning Algorithm

**Auto-Centered Labels** (x is None):
```python
if label_x_offset is None:
    # Calculate text width estimate
    estimated_width = len(label_text) * font_size * 0.6

    # Center horizontally on node
    label_x = icon_size / 2  # Center of node
    label_y = -25            # Standard above-node position
    text_anchor = "middle"   # SVG text anchor
```

**Manual-Positioned Labels** (x/y are set):
```python
else:
    # Use GNS3 position directly - NO additional calculations
    label_x = label_x_offset
    label_y = label_y_offset

    # Determine text anchor based on position relative to node center
    if abs(label_x_offset - icon_size / 2) < 5:
        text_anchor = "middle"  # Centered
    elif label_x_offset > icon_size / 2:
        text_anchor = "end"     # Right of center (right-aligned)
    else:
        text_anchor = "start"   # Left of center (left-aligned)
```

### Common Label Rendering Mistakes

**❌ WRONG - v0.6.1 and earlier:**
```python
# DON'T add estimated dimensions to stored position!
estimated_width = len(label_text) * font_size * 0.6
estimated_height = font_size * 1.5
label_x = label_x_offset + estimated_width  # ❌ Adds offset incorrectly
label_y = label_y_offset + estimated_height / 2  # ❌ Vertical misalignment
```

**✅ CORRECT - v0.6.2:**
```python
# Use stored position directly
label_x = label_x_offset  # ✅ GNS3 position is already correct
label_y = label_y_offset  # ✅ No additional calculations needed
```

### SVG Rendering Details

**CSS Styles:**
```css
.node-label {
    /* NO fixed text-anchor here - applied per-label dynamically */
    dominant-baseline: text-before-edge;  /* Vertical alignment */
}
```

**SVG Text Element:**
```svg
<text class="node-label"
      x="{label_x}"
      y="{label_y}"
      text-anchor="{text_anchor}"  <!-- Dynamic: start/middle/end -->
      transform="rotate({rotation} {label_x} {label_y})"
      style="{label_style}">
    {label_text}
</text>
```

### Font Style Formats

GNS3 uses two font format representations:

**Qt Font String** (internal GNS3 settings):
```python
"TypeWriter,10,-1,5,75,0,0,0,0,0"
# Format: Family,Size,Weight,Style,Weight2,...
```

**SVG Style String** (stored in .gns3 project file):
```python
"font-family: TypeWriter;font-size: 10.0;font-weight: bold;fill: #000000;fill-opacity: 1.0;"
```

The MCP server preserves the SVG style string from GNS3 data, ensuring visual consistency.

### Label Rotation

Labels support rotation around their anchor point:

```python
# Rotation transform applied to text element
if label_rotation != 0:
    label_transform = f'transform="rotate({label_rotation} {label_x} {label_y})"'
```

**Rotation is around**: The label's actual position (label_x, label_y), NOT the node center.

### Comparison: Official GNS3 vs MCP Export

**Before v0.6.2 (Incorrect):**
- Labels offset too far to the right (added estimated_width)
- Labels positioned too low (added half estimated_height)
- All labels right-aligned (fixed text-anchor: end)

**After v0.6.2 (Correct):**
- ✅ Labels match GNS3 GUI positions exactly
- ✅ Auto-centered labels work correctly
- ✅ Dynamic text-anchor based on position
- ✅ Rotation works as expected

### Testing Label Rendering

**Export from GNS3 GUI:**
```
File → Export portable picture → Save as PNG
```

**Export from MCP Server:**
```python
export_topology_diagram(
    output_path="C:/path/to/output",
    format="both"  # Creates .svg and .png
)
```

**Visual Comparison Checklist:**
- [ ] Node labels in identical positions
- [ ] Label text not offset to the right
- [ ] Auto-centered labels (x=None) above nodes at y=-25
- [ ] Font matches: TypeWriter, 10pt, bold, black
- [ ] Rotated labels render correctly
- [ ] Left/center/right aligned labels match position

### Implementation Files

**Label rendering logic:**
- `mcp-server/server/main.py` lines 2338-2403
  - Label position calculation (2355-2375)
  - SVG text generation (2377-2403)
  - CSS styles (2117)

**Reference implementation:**
- `gns3-gui/gns3/items/node_item.py` lines 343-393
  - Official GNS3 label centering logic (_centerLabel)
  - Label update and positioning (_updateLabel)

## Git Workflow

### Commit Messages

Follow conventional commits format:
```
feat: add new console filtering tool
fix: resolve telnet timeout issue
docs: update testing guide
test: add console reconnection tests
```

### Files to Commit

**Always commit:**
- Source code (server/*.py)
- manifest.json
- requirements.txt
- Documentation (*.md)
- Tests (tests/*.py)

**Never commit:**
- .env (contains passwords)
- lib/ folder (generated)
- *.mcpb files (generated)
- __pycache__/
- *.pyc

### Before Committing

1. Run tests
2. Update version if needed
3. Update documentation if needed
4. Stage only relevant files
5. Write descriptive commit message

## Testing Checklist

Before considering a change complete:

- [ ] Code changes tested locally
- [ ] Unit tests pass (`python tests/test_mcp_console.py`)
- [ ] Version updated in manifest.json
- [ ] Extension repackaged: `npx @anthropic-ai/mcpb pack`
- [ ] Version in build output matches manifest
- [ ] Extension reinstalled in Claude Desktop
- [ ] Integration test passes (manual test in Claude Desktop)
- [ ] No errors in Claude Desktop logs
- [ ] Documentation updated if needed
- [ ] Changes committed to git

## Performance Considerations

### Console Buffer Management

- Default: 10MB per session
- Trim at 5MB when exceeded
- Adjust `MAX_BUFFER_SIZE` in console_manager.py if needed

### Session Timeouts

- Default: 30 minutes (1800 seconds)
- Cleanup task runs periodically
- Adjust `SESSION_TIMEOUT` if needed

### Concurrent Connections

- Multiple console sessions supported
- Each session has independent buffer
- Background reader tasks run concurrently
- Test with multiple devices if adding concurrency features

## Security Notes

- Never log passwords or tokens
- GNS3 password stored in .env (gitignored)
- JWT tokens not logged
- Console output may contain sensitive info (sanitize if needed)
- Use `sensitive: true` for password fields in manifest

## API Reference

### GNS3 v3 API Endpoints

See `data/SESSION.txt` for complete traffic analysis.

Key endpoints:
- POST `/v3/access/users/authenticate` - Get JWT token
- GET `/v3/projects` - List projects
- GET `/v3/projects/{id}/nodes` - List nodes
- POST `/v3/projects/{id}/nodes/{node_id}/start` - Start node
- POST `/v3/projects/{id}/nodes/{node_id}/stop` - Stop node

### Console Ports

- Extracted from node data: `node["console"]`
- Console type: `node["console_type"]` (telnet, vnc, spice+agent, none)
- Only telnet consoles supported currently

## Resources

- MCP Docs: https://modelcontextprotocol.io/
- GNS3 Docs: https://docs.gns3.com/
- FastMCP: https://github.com/anthropics/fastmcp
- telnetlib3: https://telnetlib3.readthedocs.io/

## Quick Reference

```bash
# Common commands
cd "C:\HOME\1. Scripts\008. GNS3 MCP"

# List nodes
python tests/list_nodes_helper.py

# Test console
python tests/test_mcp_console.py --port 5014

# Package extension
cd mcp-server && npx @anthropic-ai/mcpb pack

# View logs
notepad "C:\Users\mail4\AppData\Roaming\Claude\logs\mcp-server-GNS3 Lab Controller.log"

# Git status
git status

# Commit
git add . && git commit -m "feat: description"
```
- use https://apiv3.gns3.net/ as a source of documentation for GNS3 v3 api
- rebuild desktop extensions after finishing modifications of the tools and skills
- remember to restart chat when need to update mcp server
- keep version history in CLAUDE.md