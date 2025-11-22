# Migration Guide: Global State to Dependency Injection (GM-46)

**Version**: v0.50.0
**Date**: 2025-11-22
**Status**: Phase 1 Complete - Hybrid Approach Active

## Overview

Phase 1 (GM-46) introduced a dependency injection container to replace the global state pattern. This guide helps you migrate existing code from global state access to DI-based access.

**Current Status**: Hybrid approach - both patterns coexist during transition.

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Understanding the Change](#understanding-the-change)
3. [Migration Patterns](#migration-patterns)
4. [Common Pitfalls](#common-pitfalls)
5. [Testing Strategies](#testing-strategies)
6. [Rollout Plan](#rollout-plan)

## Quick Reference

### Before (Global State - Legacy)

```python
from context import get_app

# In a tool or resource
def my_tool():
    app = get_app()
    gns3 = app.gns3
    console = app.console
    nodes = await gns3.get_nodes(project_id)
```

### After (Dependency Injection - Recommended)

```python
from interfaces import IGns3Client, IConsoleManager

# In a tool with FastMCP Context
@mcp.tool()
async def my_tool(ctx: Context):
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)
    console = deps.get(IConsoleManager)
    nodes = await gns3.get_nodes(project_id)
```

## Understanding the Change

### Why Migrate?

**Problems with Global State:**
- Hard to test (requires global setup/teardown)
- Hidden dependencies (not clear what a function needs)
- Tight coupling (can't swap implementations)
- Thread safety concerns
- Breaks dependency inversion principle

**Benefits of DI:**
- ✅ Explicit dependencies (clear function signatures)
- ✅ Easy mocking for tests
- ✅ Loose coupling (interface-based)
- ✅ Thread-safe by design
- ✅ Follows SOLID principles

### Architecture Change

**Before (Global State):**
```
┌──────────────┐
│ Tool/Resource│
└──────┬───────┘
       │ get_app()
       ↓
┌──────────────┐
│ _app (global)│ ← Single point of failure
└──────┬───────┘
       │
       ↓
  AppContext
```

**After (Dependency Injection):**
```
┌──────────────┐
│ Tool/Resource│
└──────┬───────┘
       │ ctx.lifespan_context.dependencies
       ↓
┌──────────────┐
│ Dependencies │ ← Type-safe, thread-safe container
└──────┬───────┘
       │ get(Interface)
       ↓
  Concrete Implementation
```

## Migration Patterns

### Pattern 1: Migrating MCP Tools

**Before:**
```python
@mcp.tool()
async def list_nodes(project_id: str) -> str:
    """List nodes in project"""
    from context import get_app

    app = get_app()
    nodes = await app.gns3.get_nodes(project_id)

    # Format and return
    return json.dumps(nodes)
```

**After:**
```python
@mcp.tool()
async def list_nodes(ctx: Context, project_id: str) -> str:
    """List nodes in project"""
    # Get dependencies from FastMCP context
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)

    nodes = await gns3.get_nodes(project_id)

    # Format and return
    return json.dumps(nodes)
```

**Key Changes:**
1. Add `ctx: Context` parameter (FastMCP provides this)
2. Access dependencies via `ctx.request_context.lifespan_context.dependencies`
3. Use `deps.get(Interface)` instead of `app.service`
4. Remove `from context import get_app`

### Pattern 2: Migrating Resources

**Status**: ⚠️ Resources still use global state (by necessity)

**Current (Acceptable):**
```python
class ProjectResource:
    async def get_projects(self) -> str:
        from context import get_app

        app = get_app()
        projects = await app.gns3.get_projects()
        return json.dumps(projects)
```

**Why Global is OK Here:**
- FastMCP resources don't receive Context parameter
- Resource callbacks registered during lifespan don't have access to request context
- Global state is acceptable for resources until FastMCP adds context support

**Future (When FastMCP Supports Context in Resources):**
```python
class ProjectResource:
    def __init__(self, dependencies: Dependencies):
        self.dependencies = dependencies

    async def get_projects(self) -> str:
        gns3 = self.dependencies.get(IGns3Client)
        projects = await gns3.get_projects()
        return json.dumps(projects)
```

### Pattern 3: Accessing Multiple Services

**Before:**
```python
from context import get_app

app = get_app()
gns3 = app.gns3
console = app.console
resource_mgr = app.resource_manager
```

**After:**
```python
from interfaces import IGns3Client, IConsoleManager, IResourceManager

deps = ctx.request_context.lifespan_context.dependencies
gns3 = deps.get(IGns3Client)
console = deps.get(IConsoleManager)
resource_mgr = deps.get(IResourceManager)
```

**Tip**: Create a helper function for repeated access:
```python
def get_services(ctx: Context):
    """Helper to get commonly used services"""
    deps = ctx.request_context.lifespan_context.dependencies
    return (
        deps.get(IGns3Client),
        deps.get(IConsoleManager),
        deps.get(IResourceManager)
    )

# Usage
gns3, console, resource_mgr = get_services(ctx)
```

### Pattern 4: Background Tasks with DI

**Before:**
```python
async def background_task():
    from context import get_app

    while True:
        app = get_app()
        await app.gns3.authenticate()
        await asyncio.sleep(300)
```

**After:**
```python
async def background_task(gns3: IGns3Client):
    """Pass dependencies as parameters"""
    while True:
        await gns3.authenticate()
        await asyncio.sleep(300)

# In app_lifespan
deps = context.dependencies
gns3 = deps.get(IGns3Client)
task = asyncio.create_task(background_task(gns3))
```

**Key Point**: Pass dependencies as parameters to background tasks instead of using global state.

## Common Pitfalls

### Pitfall 1: Accessing DI Container Before Initialization

**❌ Wrong:**
```python
# At module level - container not initialized yet!
deps = get_dependencies()
gns3 = deps.get(IGns3Client)
```

**✅ Correct:**
```python
# Inside function - container initialized during lifespan
@mcp.tool()
async def my_tool(ctx: Context):
    deps = ctx.request_context.lifespan_context.dependencies
    gns3 = deps.get(IGns3Client)
```

### Pitfall 2: Using Concrete Classes Instead of Interfaces

**❌ Wrong:**
```python
from gns3_client import GNS3Client

gns3 = deps.get(GNS3Client)  # Concrete class!
```

**✅ Correct:**
```python
from interfaces import IGns3Client

gns3 = deps.get(IGns3Client)  # Interface!
```

**Why**: DI container registers interfaces, not concrete classes. Using interfaces enables mocking.

### Pitfall 3: Mixing Global and DI Access

**❌ Wrong:**
```python
# Inconsistent - uses both patterns!
app = get_app()
gns3_from_global = app.gns3

deps = ctx.request_context.lifespan_context.dependencies
gns3_from_di = deps.get(IGns3Client)
```

**✅ Correct:**
```python
# Consistent - uses DI only
deps = ctx.request_context.lifespan_context.dependencies
gns3 = deps.get(IGns3Client)
console = deps.get(IConsoleManager)
```

### Pitfall 4: Forgetting to Register Services

**❌ Wrong:**
```python
# Service not registered!
my_service = deps.get(IMyNewService)  # KeyError!
```

**✅ Correct:**
```python
# In app_lifespan - register service first
dependencies.register_singleton(IMyNewService, lambda: MyNewService())

# Then use it
my_service = deps.get(IMyNewService)
```

## Testing Strategies

### Testing with DI (Easy!)

**Before (Global State - Hard to Test):**
```python
def test_my_tool():
    # Need to set up global state
    from context import set_app
    mock_app = MockAppContext()
    set_app(mock_app)

    # Test
    result = my_tool()

    # Cleanup global state
    from context import clear_app
    clear_app()
```

**After (DI - Easy to Test):**
```python
def test_my_tool():
    # Create mock dependencies
    mock_deps = Dependencies()
    mock_gns3 = Mock(spec=IGns3Client)
    mock_deps.register_instance(IGns3Client, mock_gns3)

    # Create mock context
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context.dependencies = mock_deps

    # Test - clean and isolated!
    result = my_tool(mock_ctx)

    # No cleanup needed
```

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, MagicMock
from di_container import Dependencies
from interfaces import IGns3Client

@pytest.fixture
def mock_context_with_gns3():
    """Fixture providing mocked FastMCP context with GNS3 client"""
    mock_deps = Dependencies()
    mock_gns3 = Mock(spec=IGns3Client)
    mock_gns3.get_nodes.return_value = [{"node_id": "123", "name": "R1"}]
    mock_deps.register_instance(IGns3Client, mock_gns3)

    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context.dependencies = mock_deps

    return mock_ctx, mock_gns3

def test_list_nodes(mock_context_with_gns3):
    """Test list_nodes tool with mocked dependencies"""
    ctx, mock_gns3 = mock_context_with_gns3

    # Call tool
    result = list_nodes(ctx, project_id="abc123")

    # Verify
    mock_gns3.get_nodes.assert_called_once_with("abc123")
    assert "R1" in result
```

## Rollout Plan

### Phase 1: Foundation (✅ Complete)
- ✅ Create DI container (di_container.py)
- ✅ Integrate with app lifecycle (app.py)
- ✅ Add context helpers (context.py)
- ✅ 100% test coverage

### Phase 2: Migrate Tools (Planned)
- [ ] Audit all tools using global state
- [ ] Migrate tools one-by-one to DI
- [ ] Update tests for each migrated tool
- [ ] Verify no regressions

### Phase 3: Migrate Resources (Pending FastMCP)
- [ ] Wait for FastMCP to support Context in resources
- [ ] Or: Pass dependencies to ResourceManager constructor
- [ ] Migrate resource callbacks to use DI
- [ ] Remove global state from resources

### Phase 4: Remove Global State (Target)
- [ ] Deprecate get_app() / set_app() / clear_app()
- [ ] Remove _app global variable
- [ ] Pure DI architecture achieved

### Migration Priority

**High Priority (Migrate First):**
- New tools being developed
- Tools with complex dependencies
- Tools that are frequently modified

**Low Priority (Migrate Later):**
- Stable tools with minimal dependencies
- Tools that are rarely modified
- Simple wrapper tools

**Don't Migrate Yet:**
- Resources (wait for FastMCP support)
- Background tasks in app.py (already using DI)

## Decision Matrix: When to Use What

| Situation | Use DI | Use Global | Notes |
|-----------|--------|------------|-------|
| New tool development | ✅ | ❌ | Always use DI for new code |
| Existing tool refactor | ✅ | ❌ | Migrate to DI when touching code |
| Resource callbacks | ❌ | ✅ | Global OK until FastMCP adds context |
| Background tasks | ✅ | ❌ | Pass deps as parameters |
| Unit tests | ✅ | ❌ | DI makes testing much easier |
| Quick prototype | 🟨 | 🟨 | Either is fine for throwaway code |

Legend: ✅ Recommended | ❌ Avoid | 🟨 Acceptable

## Getting Help

**Questions?**
- Check [DI_USAGE_GUIDE.md](DI_USAGE_GUIDE.md) for patterns and examples
- Review [ADR-006-dependency-injection.md](architecture/decisions/ADR-006-dependency-injection.md) for design rationale
- See [GLOBAL_STATE_TRANSITION.md](GLOBAL_STATE_TRANSITION.md) for roadmap

**Found a bug or issue?**
- Create issue in YouTrack with tag `GM-DI-Migration`
- Include before/after code examples
- Describe expected vs actual behavior

---

**Last Updated**: 2025-11-22
**Related**: GM-46, GM-47, GM-48
**Status**: Living document - updated as migration progresses
