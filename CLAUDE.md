# GNS3 MCP Server - Project Instructions

Project-specific instructions for working with the GNS3 MCP server codebase.

## Project Overview

MCP server providing programmatic access to GNS3 network simulation labs. Includes:
- Desktop extension (.mcpb) for Claude Desktop
- Agent skill with GNS3 procedural knowledge
- Console management for device interaction
- GNS3 v3 API client with JWT authentication

## Version Management

**CRITICAL**: Update extension version every time a change is made.

- **Bugfix**: Increment patch version (0.1.1 → 0.1.2)
- **New feature**: Increment minor version (0.1.2 → 0.2.0)
- **Breaking change**: Increment major version (0.2.0 → 1.0.0)

**Version Synchronization:**
- Server code and desktop extension (.mcpb) must have the **same version**
- Always update manifest.json AND rebuild .mcpb after version changes
- If versions mismatch, Claude Desktop may use outdated code

**Steps to update version:**
1. Edit `mcp-server/manifest.json` - update `"version"` field
2. Rebuild extension: `cd mcp-server && npx @anthropic-ai/mcpb pack`
3. Verify version in output: `gns3-mcp@X.Y.Z`
4. Reinstall in Claude Desktop (double-click .mcpb)

## File Structure

```
008. GNS3 MCP/
├── mcp-server/
│   ├── server/
│   │   ├── main.py              # FastMCP server (12 tools)
│   │   ├── gns3_client.py       # GNS3 v3 API client
│   │   └── console_manager.py   # Telnet console manager
│   ├── lib/                     # Bundled Python dependencies
│   ├── manifest.json            # Desktop extension manifest
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
├── requirements.txt             # Python dependencies
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
```

**After editing:**
1. Test locally first (see Testing section)
2. Update version in manifest.json (increment appropriately)
3. Repackage extension: `cd mcp-server && npx @anthropic-ai/mcpb pack`
4. Verify version in build output matches manifest
5. Reinstall and test in Claude Desktop

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
pip install --target=lib mcp httpx telnetlib3
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
