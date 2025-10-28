# GNS3 MCP Server - Project Instructions

Project-specific instructions for working with the GNS3 MCP server codebase.

## Project Overview

MCP server providing programmatic access to GNS3 network simulation labs. Includes:
- Desktop extension (.mcpb) for Claude Desktop
- Agent skill with GNS3 procedural knowledge
- Console management for device interaction
- GNS3 v3 API client with JWT authentication

## Current Version: v0.30.0

**Latest Release:** v0.30.0 - Table Mode & Resource Improvements (BREAKING CHANGES)

### Recent Changes (v0.26.0 - v0.30.0)

**v0.30.0** - **BREAKING**: Table mode output, URIs instead of IDs, proxy type field
**v0.29.1** - Dual access patterns for sessions (path-based + query-param)
**v0.29.0** - **BREAKING**: Resource URI scheme changes, complete metadata, linting infrastructure
**v0.28.0** - Local execution on SSH proxy container (ssh_command with node_name="@")
**v0.27.0** - Configurable SSH session timeouts
**v0.26.0** - Multi-proxy support for isolated network access

### Current State
- **27 Tools**: Complete GNS3 lab automation toolkit including Docker file operations
- **21 Resources**: Text table output (simple style), URIs instead of IDs, complete metadata
- **5 Prompts**: Guided workflows for SSH setup, topology discovery, troubleshooting, lab setup, node setup
- **Code Quality**: Ruff, Mypy, Black linting with pre-commit hooks
- **Project Memory**: Per-project README for IP schemes, credentials, architecture notes
- **Table Output**: All list resources use tabulate library with "simple" style (no borders)

For complete version history and detailed release notes, see [CHANGELOG.md](CHANGELOG.md).

## Code Quality Standards

### Linting Tools
- **Ruff**: Fast Python linter (replaces flake8, isort, pyupgrade) - 10-100x faster
- **Mypy**: Static type checker - catches type errors before runtime
- **Black**: Opinionated code formatter - consistent style across codebase
- **Pre-commit**: Automated quality checks on every commit

### Running Linters Manually

```bash
# Check all issues (no changes)
ruff check mcp-server/server/

# Auto-fix safe issues
ruff check --fix mcp-server/server/

# Format code (modifies files)
black mcp-server/server/

# Type check (reports issues)
mypy mcp-server/server/
```

### Pre-commit Hooks

Automatically run on every commit (configured in `.pre-commit-config.yaml`):
1. **Ruff linter** - checks code quality, auto-fixes safe issues
2. **Ruff formatter** - formats code consistently
3. **Black formatter** - additional formatting
4. **Mypy type checker** - static type analysis
5. **Update lib dependencies** - cleans and reinstalls lib/ when requirements.txt changes
6. **Build extension** - rebuilds .mcpb if server code, manifest.json, or requirements.txt changed

Install hooks:
```bash
pre-commit install
```

Test hooks without committing:
```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run
```

### Configuration Files

All linting configuration centralized in [pyproject.toml](pyproject.toml):

**Key Settings:**
- Line length: 100 characters
- Target: Python 3.9+
- Excludes: `mcp-server/lib/` (vendored dependencies)
- Type checking: Lenient (can be tightened incrementally)

**Ignored Rules:**
- `E501` - Line too long (Black handles this)
- `B008` - Function calls in defaults (FastMCP decorator pattern)
- `UP006/UP007` - Allow `Optional`, `List` for clarity (Python 3.9+ style also supported)

### Code Style Guidelines

**Type Hints:**
- Use type hints for all public functions
- Can use either `List`/`Dict` or `list`/`dict` (both accepted)
- Prefer `Optional[T]` over `T | None` for clarity

**Imports:**
- Automatically sorted by Ruff
- Unused imports automatically removed
- `__init__.py` files can have unused imports (F401 ignored)

**Docstrings:**
- All public functions have docstrings
- Current style: Mixed (Google + reStructuredText)
- Include: purpose, args, returns, examples

**Error Handling:**
- Use structured error responses (`ErrorResponse` model)
- Log errors with appropriate levels
- Don't expose sensitive data in errors

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

### Regenerate Activity Diagrams

**Location**: `mcp-server/docs/diagrams/`

When modifying `.puml` files, manually regenerate SVG files:

```bash
# Regenerate all diagrams
java -jar plantuml.jar -tsvg mcp-server/docs/diagrams/*.puml

# Regenerate specific diagram
java -jar plantuml.jar -tsvg mcp-server/docs/diagrams/ssh_setup_workflow.puml
```

**Note**: SVG generation is NOT automatic on commit (removed from pre-commit hook due to Windows incompatibility). Always regenerate and commit SVG files when updating .puml sources.

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

## Resource URI Patterns

MCP resources use semantic URI schemes for different resource types:

### URI Scheme Categories

**Project-centric resources:**
- `projects://` - List all projects
- `projects://{id}` - Project details
- `projects://{id}/readme` - Project README/notes
- `projects://{id}/sessions/console/` - Console sessions in project
- `projects://{id}/sessions/ssh/` - SSH sessions in project

**Object-centric resources:**
- `nodes://{project_id}/` - Nodes in project
- `nodes://{project_id}/{node_id}` - Node details
- `nodes://{project_id}/{node_id}/template` - Node template usage
- `links://{project_id}/` - Links in project
- `drawings://{project_id}/` - Drawings in project

**Template resources (static, not project-scoped):**
- `templates://` - List all templates
- `templates://{template_id}` - Template details

**Session resources (dual access patterns):**
- `sessions://console/` - All console sessions
- `sessions://console/?project_id={id}` - Console sessions filtered by project (query param)
- `sessions://console/{node_name}` - Console session for specific node
- `sessions://ssh/` - All SSH sessions
- `sessions://ssh/?project_id={id}` - SSH sessions filtered by project (query param)
- `sessions://ssh/{node_name}` - SSH session for specific node
- `sessions://ssh/{node_name}/history` - SSH command history
- `sessions://ssh/{node_name}/buffer` - SSH continuous buffer

**Proxy resources:**
- `proxies:///status` - Main proxy status (THREE slashes)
- `proxies://` - Proxy registry
- `proxies://sessions` - All proxy sessions
- `proxies://project/{project_id}` - Proxies for specific project
- `proxies://{proxy_id}` - Specific proxy details

### Dual Access Patterns for Sessions

Session resources support both path-based and query-parameter-based access:

**Path-based (project-centric):**
```
projects://{project_id}/sessions/console/
projects://{project_id}/sessions/ssh/
```
Returns sessions for nodes in the specified project.

**Query-parameter-based (filtered):**
```
sessions://console/?project_id={id}
sessions://ssh/?project_id={id}
```
Returns same results as path-based, but using query parameter filtering.

**Unfiltered access:**
```
sessions://console/
sessions://ssh/
```
Returns all sessions across all projects.

**Implementation notes:**
- ResourceManager.parse_uri() handles query parameter extraction
- Session handlers accept optional `project_id` parameter
- Implementation filters by project when parameter provided
- All three access methods return same data structure

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
- Remember that you need to update the version and set the 'latest' tag to the container