# Dependency Injection Usage Guide

**Version**: v0.50.0
**Date**: 2025-11-22
**Audience**: Developers building tools and resources for GNS3 MCP

## Table of Contents

1. [Quick Start](#quick-start)
2. [Service Lifetimes](#service-lifetimes)
3. [Usage Patterns](#usage-patterns)
4. [Testing with DI](#testing-with-di)
5. [Best Practices](#best-practices)
6. [Anti-Patterns](#anti-patterns)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### Basic Tool with DI

```python
from fastmcp import Context
from interfaces import IGns3Client

@mcp.tool()
async def list_nodes(ctx: Context, project_id: str) -> str:
    """List all nodes in a project"""
    # 1. Get dependencies from FastMCP context
    deps = ctx.request_context.lifespan_context.dependencies

    # 2. Retrieve service by interface
    gns3 = deps.get(IGns3Client)

    # 3. Use service
    nodes = await gns3.get_nodes(project_id)

    return json.dumps(nodes, indent=2)
```

**Three simple steps**:
1. Access DI container via FastMCP context
2. Get service using interface type
3. Use the service

### Available Services

| Interface | Description | Registered As |
|-----------|-------------|---------------|
| `IGns3Client` | GNS3 v3 API client | Singleton |
| `IConsoleManager` | Telnet console manager | Singleton |
| `IResourceManager` | MCP resource manager | Singleton |
| `IAppContext` | Application context | Singleton |

## Service Lifetimes

The DI container supports three lifetimes:

### 1. Singleton (Shared Instance)

**When**: Service is stateless or maintains shared state
**Example**: GNS3Client, ConsoleManager

```python
# Registered once during app startup
dependencies.register_singleton(
    IGns3Client,
    lambda: GNS3Client(host="...", port=80, ...)
)

# Every call gets the SAME instance
gns3_1 = deps.get(IGns3Client)
gns3_2 = deps.get(IGns3Client)
assert gns3_1 is gns3_2  # ✅ Same object
```

**Characteristics**:
- Created lazily on first `get()` call
- Thread-safe initialization (double-check locking)
- Memory efficient (one instance shared)
- Fast retrieval after first creation

### 2. Transient (New Instance Each Time)

**When**: Service maintains per-operation state
**Example**: Report generators, temporary processors

```python
# Registered with factory
dependencies.register_transient(
    IReportGenerator,
    lambda: ReportGenerator()
)

# Every call gets a NEW instance
report_1 = deps.get(IReportGenerator)
report_2 = deps.get(IReportGenerator)
assert report_1 is not report_2  # ✅ Different objects
```

**Characteristics**:
- Created fresh on every `get()` call
- No shared state between instances
- Higher memory usage
- Useful for stateful operations

### 3. Instance (Pre-Created Singleton)

**When**: Service already exists (created during startup)
**Example**: AppContext itself

```python
# Register existing object
context = AppContext(gns3=..., console=..., dependencies=...)
dependencies.register_instance(IAppContext, context)

# Get the pre-created instance
app = deps.get(IAppContext)
assert app is context  # ✅ Same object
```

**Characteristics**:
- Instance created before registration
- Immediately available (no lazy init)
- Behaves like singleton
- Useful for circular dependencies

## Usage Patterns

### Pattern 1: Simple Service Access

**Use Case**: Tool needs one service

```python
@mcp.tool()
async def get_gns3_version(ctx: Context) -> str:
    """Get GNS3 server version"""
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)

    version_info = await gns3.get_version()
    return f"GNS3 Server: {version_info['version']}"
```

### Pattern 2: Multiple Services

**Use Case**: Tool needs multiple services

```python
@mcp.tool()
async def connect_and_send(ctx: Context, node_name: str, command: str) -> str:
    """Connect to node console and send command"""
    # Get all needed services
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)
    console = deps.get(IConsoleManager)
    app = deps.get(IAppContext)

    # Use services
    project_id = app.current_project_id
    nodes = await gns3.get_nodes(project_id)

    # Find node
    node = next((n for n in nodes if n["name"] == node_name), None)
    if not node:
        return f"Node {node_name} not found"

    # Connect and send
    session_id = await console.connect(node["console_host"], node["console"], node_name)
    await console.send(session_id, command + "\n")

    return "Command sent successfully"
```

### Pattern 3: Helper Function for Common Access

**Use Case**: Reduce boilerplate in multiple tools

```python
# Create helper in shared module
def get_common_services(ctx: Context):
    """Helper to get commonly used services"""
    deps = ctx.request_context.lifespan_context.dependencies
    return (
        deps.get(IGns3Client),
        deps.get(IConsoleManager),
        deps.get(IAppContext)
    )

# Use in tools
@mcp.tool()
async def my_tool(ctx: Context) -> str:
    gns3, console, app = get_common_services(ctx)

    # Use services directly
    nodes = await gns3.get_nodes(app.current_project_id)
    return json.dumps(nodes)
```

### Pattern 4: Conditional Service Access

**Use Case**: Only access service if needed

```python
@mcp.tool()
async def conditional_tool(ctx: Context, use_console: bool) -> str:
    """Tool that optionally uses console"""
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)  # Always needed

    nodes = await gns3.get_nodes("project-123")

    if use_console:
        # Only get console service when needed
        console = deps.get(IConsoleManager)
        # Use console...

    return json.dumps(nodes)
```

### Pattern 5: Background Task with Dependencies

**Use Case**: Async background task needs services

```python
async def periodic_health_check(gns3: IGns3Client):
    """Background task - dependencies passed as parameters"""
    while True:
        try:
            await gns3.authenticate()
            logger.info("Health check passed")
        except Exception as e:
            logger.error(f"Health check failed: {e}")

        await asyncio.sleep(60)

# In app_lifespan
deps = context.dependencies
gns3 = deps.get(IGns3Client)

# Pass dependency as parameter
health_task = asyncio.create_task(periodic_health_check(gns3))
```

**Key Point**: Pass dependencies to background tasks instead of accessing container inside task.

## Testing with DI

### Pattern 1: Basic Mock Setup

```python
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from di_container import Dependencies
from interfaces import IGns3Client

@pytest.fixture
def mock_context():
    """Fixture providing mocked FastMCP context"""
    # Create DI container
    mock_deps = Dependencies()

    # Register mock services
    mock_gns3 = Mock(spec=IGns3Client)
    mock_gns3.get_nodes = AsyncMock(return_value=[
        {"node_id": "123", "name": "Router1"}
    ])
    mock_deps.register_instance(IGns3Client, mock_gns3)

    # Create FastMCP context
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context.dependencies = mock_deps

    return mock_ctx, mock_gns3

def test_list_nodes(mock_context):
    """Test list_nodes tool with mocked GNS3 client"""
    ctx, mock_gns3 = mock_context

    result = await list_nodes(ctx, project_id="abc123")

    # Verify mock was called
    mock_gns3.get_nodes.assert_called_once_with("abc123")
    assert "Router1" in result
```

### Pattern 2: Multiple Mock Services

```python
@pytest.fixture
def full_mock_context():
    """Fixture with all services mocked"""
    mock_deps = Dependencies()

    # Mock GNS3 client
    mock_gns3 = Mock(spec=IGns3Client)
    mock_gns3.get_nodes = AsyncMock(return_value=[])
    mock_deps.register_instance(IGns3Client, mock_gns3)

    # Mock console manager
    mock_console = Mock(spec=IConsoleManager)
    mock_console.connect = AsyncMock(return_value="session-123")
    mock_deps.register_instance(IConsoleManager, mock_console)

    # Mock app context
    mock_app = Mock(spec=IAppContext)
    mock_app.current_project_id = "test-project"
    mock_deps.register_instance(IAppContext, mock_app)

    # Create context
    ctx = MagicMock()
    ctx.request_context.lifespan_context.dependencies = mock_deps

    return ctx, (mock_gns3, mock_console, mock_app)
```

### Pattern 3: Partial Mocking (Real + Mock)

```python
def test_with_real_console():
    """Use real ConsoleManager but mock GNS3Client"""
    mock_deps = Dependencies()

    # Mock GNS3 (external API)
    mock_gns3 = Mock(spec=IGns3Client)
    mock_deps.register_instance(IGns3Client, mock_gns3)

    # Real console manager (no external dependencies)
    real_console = ConsoleManager()
    mock_deps.register_instance(IConsoleManager, real_console)

    # Test with mix of real and mock
    ctx = create_mock_context(mock_deps)
    # ... test code
```

## Best Practices

### ✅ DO

1. **Use Interfaces, Not Concrete Classes**
   ```python
   ✅ gns3 = deps.get(IGns3Client)
   ❌ gns3 = deps.get(GNS3Client)
   ```

2. **Access Container Once Per Function**
   ```python
   ✅ deps = ctx.request_context.lifespan_context.dependencies
      gns3 = deps.get(IGns3Client)
      console = deps.get(IConsoleManager)

   ❌ gns3 = ctx.request_context.lifespan_context.dependencies.get(IGns3Client)
      console = ctx.request_context.lifespan_context.dependencies.get(IConsoleManager)
   ```

3. **Pass Dependencies to Background Tasks**
   ```python
   ✅ async def task(gns3: IGns3Client):
          await gns3.authenticate()

   ❌ async def task():
          gns3 = get_app().gns3  # Global state!
   ```

4. **Create Fixtures for Tests**
   ```python
   ✅ @pytest.fixture
      def mock_context():
          # Reusable mock setup
          return create_mocked_context()

   ❌ def test_something():
          # Inline mock setup (repeated)
          mock_deps = Dependencies()
          # ... setup code in every test
   ```

### ❌ DON'T

1. **Don't Mix Global and DI Access**
   ```python
   ❌ gns3_from_global = get_app().gns3
      gns3_from_di = deps.get(IGns3Client)
      # Pick one!
   ```

2. **Don't Access Container at Module Level**
   ```python
   ❌ # Module level - container not initialized!
      deps = get_dependencies()
      GNS3_CLIENT = deps.get(IGns3Client)

   ✅ # Inside function - container initialized
      def my_function(ctx: Context):
          deps = ctx.request_context.lifespan_context.dependencies
          gns3 = deps.get(IGns3Client)
   ```

3. **Don't Register Services Inside Tools**
   ```python
   ❌ def my_tool(ctx: Context):
          deps = ctx.request_context.lifespan_context.dependencies
          deps.register_singleton(...)  # Wrong place!

   ✅ # In app_lifespan only
      async def app_lifespan(server):
          deps = Dependencies()
          deps.register_singleton(...)
   ```

4. **Don't Catch KeyError on Missing Service**
   ```python
   ❌ try:
          gns3 = deps.get(IGns3Client)
      except KeyError:
          gns3 = None  # Hiding configuration error!

   ✅ # Let it fail - missing service is a bug
      gns3 = deps.get(IGns3Client)
   ```

## Anti-Patterns

### Anti-Pattern 1: Service Locator

**Problem**: Using DI container as service locator everywhere

```python
❌ # Anti-pattern: Passing container around
def process_nodes(deps: Dependencies, project_id: str):
    gns3 = deps.get(IGns3Client)
    console = deps.get(IConsoleManager)
    # ...

def another_function(deps: Dependencies):
    result = process_nodes(deps, "abc123")
```

**Solution**: Pass services, not container

```python
✅ # Better: Explicit dependencies
def process_nodes(gns3: IGns3Client, console: IConsoleManager, project_id: str):
    # Uses services directly
    # ...

def another_function(ctx: Context):
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)
    console = deps.get(IConsoleManager)

    result = process_nodes(gns3, console, "abc123")
```

### Anti-Pattern 2: God Object

**Problem**: Putting everything in one service

```python
❌ # Anti-pattern: One service does everything
class MegaService:
    def get_nodes(self): ...
    def start_node(self): ...
    def connect_console(self): ...
    def send_ssh_command(self): ...
    # 50+ methods...

deps.register_singleton(IMegaService, lambda: MegaService())
```

**Solution**: Separate concerns

```python
✅ # Better: Single responsibility
deps.register_singleton(IGns3Client, lambda: GNS3Client())
deps.register_singleton(IConsoleManager, lambda: ConsoleManager())
deps.register_singleton(ISshManager, lambda: SshManager())
```

### Anti-Pattern 3: Temporal Coupling

**Problem**: Services must be accessed in specific order

```python
❌ # Anti-pattern: Order-dependent access
gns3 = deps.get(IGns3Client)
gns3.initialize()  # Must call before using!
nodes = await gns3.get_nodes(...)  # Breaks if init not called
```

**Solution**: Services self-initialize

```python
✅ # Better: Service handles initialization
class GNS3Client:
    async def get_nodes(self, project_id: str):
        await self._ensure_authenticated()  # Auto-initializes
        # ... actual implementation
```

## Troubleshooting

### Error: "Service not registered"

```python
KeyError: "Service not registered: INewService. Available services: IGns3Client, IConsoleManager"
```

**Cause**: Service not registered in app_lifespan
**Fix**: Add registration in `app.py`:

```python
# In app_lifespan
dependencies.register_singleton(INewService, lambda: NewService())
```

### Error: "Application not initialized"

```python
RuntimeError: "Application not initialized"
```

**Cause**: Accessing `get_app()` or `get_dependencies()` before app startup
**Fix**: Only access inside tools/resources, not at module level

### Service Always Returns Same Instance (Transient Bug)

**Cause**: Registered as singleton instead of transient
**Fix**: Change registration:

```python
❌ dependencies.register_singleton(IReport, lambda: Report())
✅ dependencies.register_transient(IReport, lambda: Report())
```

### Type Checker Complains About Service Type

**Cause**: Using concrete class instead of interface
**Fix**: Import and use interface type:

```python
❌ from gns3_client import GNS3Client
   gns3: GNS3Client = deps.get(IGns3Client)  # Type mismatch!

✅ from interfaces import IGns3Client
   gns3: IGns3Client = deps.get(IGns3Client)  # Correct!
```

## Further Reading

- [MIGRATION_GM-46.md](MIGRATION_GM-46.md) - Migrating from global state
- [ADR-006-dependency-injection.md](architecture/decisions/ADR-006-dependency-injection.md) - Design decisions
- [GLOBAL_STATE_TRANSITION.md](GLOBAL_STATE_TRANSITION.md) - Transition roadmap
- [di_container.py](../gns3_mcp/server/di_container.py) - Implementation
- [test_di_container.py](../tests/unit/test_di_container.py) - Test examples

---

**Last Updated**: 2025-11-22
**Version**: v0.50.0
**Status**: Living document - updated as patterns emerge
