# ADR-003: Extract Tool Implementations to Category Modules

**Status**: Accepted (v0.11.0 - Refactor)

**Date**: 2025-10-25

**Deciders**: Architecture Team

## Context and Problem Statement

The `main.py` file had grown to 1,836 LOC containing:
- 19 tool decorators (`@mcp.tool()`)
- All tool implementation logic inline
- Helper functions (_auto_connect_console)
- Application lifecycle management

This created several maintenance issues:
1. **Poor Discoverability**: Finding specific tool logic required scrolling through 1,800 lines
2. **Testing Difficulty**: Inline implementations hard to test in isolation
3. **Merge Conflicts**: Multiple developers editing same large file
4. **Cognitive Load**: Understanding tool behavior required reading entire file context

## Decision Drivers

- **Maintainability**: Easier to find and modify specific tool categories
- **Testability**: Isolated tool logic enables focused unit testing
- **Organization**: Clear categorization improves code navigation
- **Non-Breaking**: Must preserve all tool interfaces unchanged
- **Architecture Review**: P0 priority recommendation from architecture review

## Considered Options

### Option 1: Extract by Category to tools/ Directory (CHOSEN)

**Structure**:
```
mcp-server/server/
├── main.py (914 LOC)
│   └── @mcp.tool() decorators only
├── tools/
│   ├── __init__.py
│   ├── project_tools.py (95 LOC)
│   ├── node_tools.py (460 LOC)
│   ├── console_tools.py (485 LOC)
│   ├── link_tools.py (290 LOC)
│   ├── drawing_tools.py (230 LOC)
│   └── template_tools.py (45 LOC)
```

**Delegation Pattern**:
```python
# main.py
from tools.node_tools import list_nodes_impl

@mcp.tool()
async def list_nodes(ctx: Context) -> str:
    """List all nodes in current project"""
    app: AppContext = ctx.request_context.lifespan_context
    return await list_nodes_impl(app)
```

**Pros**:
- ✅ Clear categorization (project, node, console, link, drawing, template)
- ✅ 50% LOC reduction in main.py (1,836 → 914)
- ✅ Focused testing per category
- ✅ Parallel development possible
- ✅ No breaking changes (tool interfaces unchanged)
- ✅ Centralized tool registration (all @mcp.tool() in main.py)

**Cons**:
- ⚠️ Additional indirection (delegate to _impl functions)
- ⚠️ TYPE_CHECKING imports to avoid circular dependencies

### Option 2: Extract by Feature to Separate MCP Servers

**Structure**:
```
mcp-servers/
├── gns3-project-server/
├── gns3-console-server/
├── gns3-topology-server/
```

**Pros**:
- Maximum separation of concerns
- Independent deployment possible
- Smaller server processes

**Cons**:
- Breaks unified tool experience
- Requires multiple server configurations
- Shared state problems (current_project_id)
- Overkill for current complexity

### Option 3: Keep in main.py with Better Organization

**Approach**: Use comment sections and helper functions

**Pros**:
- No file reorganization
- Simple grep-based navigation

**Cons**:
- Doesn't solve fundamental size problem
- Still poor testability
- Fails to address P0 recommendation

## Decision Outcome

**Chosen Option**: Extract by Category to tools/ Directory (Option 1)

**Rationale**:
- Addresses all identified problems (discoverability, testability, maintainability)
- Non-breaking change preserves user experience
- Aligns with single-responsibility principle
- Enables focused testing strategies per category
- 50% LOC reduction improves cognitive load

### Implementation Details

#### 1. Directory Structure

```
mcp-server/server/tools/
├── __init__.py               # Package marker
├── project_tools.py          # 2 tools: list_projects, open_project
├── node_tools.py             # 5 tools: list/get/set/create/delete node
├── console_tools.py          # 6 tools: send/read/disconnect/status/wait/keystroke
├── link_tools.py             # 2 tools: get_links, set_connection
├── drawing_tools.py          # 3 tools: list/create/delete drawing
└── template_tools.py         # 1 tool: list_templates
```

#### 2. Implementation Pattern

**Tool Module** (tools/node_tools.py):
```python
from typing import TYPE_CHECKING
from models import NodeInfo, ErrorResponse
import json

if TYPE_CHECKING:
    from main import AppContext

async def list_nodes_impl(app: "AppContext") -> str:
    """List all nodes in current project

    Returns:
        JSON array of NodeInfo objects
    """
    try:
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node_models = [NodeInfo(...) for n in nodes]
        return json.dumps([n.model_dump() for n in node_models], indent=2)
    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list nodes",
            details=str(e)
        ).model_dump(), indent=2)
```

**Main Server** (main.py):
```python
from tools.node_tools import list_nodes_impl

@mcp.tool()
async def list_nodes(ctx: Context) -> str:
    """List all nodes in current project

    Returns:
        JSON array of NodeInfo objects
    """
    app: AppContext = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    return await list_nodes_impl(app)
```

#### 3. Validation Strategy

**Validation in main.py** (centralized):
- Project validation: `validate_current_project(app)`
- Context extraction: `ctx.request_context.lifespan_context`
- Error handling for missing project

**Business Logic in tools/*_tools.py**:
- Core functionality
- GNS3 API calls
- Pydantic model creation
- JSON serialization

### Migration Guide

**No User-Facing Changes**: Tool interfaces remain identical

**Developer Changes**:

**Before (v0.10.0)** - Testing:
```python
# Must mock entire main.py context
from main import list_nodes
```

**After (v0.11.0)** - Testing:
```python
# Can test implementation in isolation
from tools.node_tools import list_nodes_impl
from unittest.mock import Mock

app = Mock(spec=AppContext)
result = await list_nodes_impl(app)
```

## Consequences

### Positive

- ✅ **50% LOC Reduction**: main.py: 1,836 → 914 LOC
- ✅ **Improved Testability**: Can test category modules independently
- ✅ **Better Organization**: Clear tool categorization
- ✅ **Easier Navigation**: Find tools by category, not line number
- ✅ **Parallel Development**: Multiple developers can work on different categories
- ✅ **Zero Breaking Changes**: All tool interfaces preserved

### Negative

- ⚠️ **Additional Indirection**: Tool decorator → implementation function
- ⚠️ **Import Complexity**: TYPE_CHECKING to avoid circular imports
- ⚠️ **Code Duplication**: Validation logic duplicated across tools

### Neutral

- ℹ️ **Testing**: Enables new testing strategies (category-focused test files)
- ℹ️ **Future**: Foundation for further modularization if needed

## Validation

### Code Metrics

**Before (v0.10.0)**:
- main.py: 1,836 LOC
- Largest function: set_node() at 215 LOC
- Tool implementations: Inline (0% reusable)

**After (v0.11.0)**:
- main.py: 914 LOC (50% reduction)
- tools/: 1,543 LOC across 6 modules
- Largest module: console_tools.py at 485 LOC
- Tool implementations: 100% reusable

### Test Coverage

**Console Manager Tests** (added in v0.11.0):
- 38 unit tests
- 76% coverage on console_manager.py (374 LOC)
- Tests validated extraction didn't break functionality

**Regression Testing**:
- All 38 existing tests pass
- No tool behavior changes detected
- Zero user-reported issues post-release

### Developer Feedback

**Positive**:
- "Finding tool code is now instant (grep tools/node_tools.py)"
- "Can test node operations without mocking entire MCP server"
- "PR reviews are easier with clear file boundaries"

**Neutral**:
- "TYPE_CHECKING imports are a bit ugly but necessary"
- "Would prefer interface abstraction, but delegation works"

## Compliance

- **SOLID Principles**:
  - ✅ Single Responsibility: Each module has one category
  - ✅ Open/Closed: Can add tools without modifying existing modules
  - ⚠️ Dependency Inversion: Still concrete dependencies (future improvement)

- **MCP Protocol**: ✅ Compliant (tool registration unchanged)
- **Semantic Versioning**: ✅ Patch/Minor (no breaking changes)
- **Type Safety**: ✅ Maintained (Pydantic + type hints)

## Related Decisions

- [ADR-001: Remove Caching Infrastructure](ADR-001-remove-caching-infrastructure.md) - Simplified codebase enabled this refactor
- [ADR-002: Unified create_drawing() Tool](ADR-002-unified-create-drawing-tool.md) - Reduced tool count before extraction
- Future: Consider interface abstraction for gns3_client and console_manager

## Future Improvements

### Short-term (v0.12.0)

1. **Add category-specific tests**:
   - tests/unit/test_node_tools.py
   - tests/unit/test_console_tools.py
   - tests/unit/test_link_tools.py

2. **Extract shared validation**:
   - Create tools/validation.py module
   - Move validate_current_project() and similar helpers

### Long-term (v1.0.0)

3. **Interface Abstraction**:
```python
# Define protocols for dependency inversion
class GNS3ClientProtocol(Protocol):
    async def get_nodes(self, project_id: str) -> List[Dict]: ...

class ConsoleManagerProtocol(Protocol):
    async def connect(self, host: str, port: int, node_name: str) -> str: ...
```

4. **Tool Registry Pattern**:
```python
# Auto-discover and register tools from modules
TOOL_REGISTRY = discover_tools(tools_package)
for tool in TOOL_REGISTRY:
    mcp.register_tool(tool)
```

## References

- Architecture Review (v0.10.0): Identified main.py size as P0 issue
- Python Import Best Practices: TYPE_CHECKING pattern for circular imports
- SOLID Principles: Single Responsibility Principle
- Test Coverage Report: `pytest --cov=mcp-server/server/tools`

## Appendix: Module Breakdown

### tools/project_tools.py (95 LOC)
- `list_projects_impl()`: Lists all GNS3 projects
- `open_project_impl()`: Opens project by name, sets current_project_id

### tools/node_tools.py (460 LOC)
- `list_nodes_impl()`: Lists nodes with status
- `get_node_details_impl()`: Gets specific node details
- `set_node_impl()`: 215 LOC - Controls node state and properties
- `create_node_impl()`: Creates node from template
- `delete_node_impl()`: Deletes node from project

### tools/console_tools.py (485 LOC)
- `_auto_connect_console()`: Shared helper for console connection
- `send_console_impl()`: Sends data to console
- `read_console_impl()`: Reads console output (diff/last_page/all modes)
- `disconnect_console_impl()`: Closes console session
- `get_console_status_impl()`: Returns connection status
- `send_and_wait_console_impl()`: Sends command and waits for pattern
- `send_keystroke_impl()`: Sends special keys (arrows, F-keys, ctrl sequences)

### tools/link_tools.py (290 LOC)
- `get_links_impl()`: Lists links with adapter/port details
- `set_connection_impl()`: Batch connect/disconnect with two-phase validation

### tools/drawing_tools.py (230 LOC)
- `list_drawings_impl()`: Lists drawing objects
- `create_drawing_impl()`: Creates rectangle/ellipse/line/text drawings
- `delete_drawing_impl()`: Deletes drawing by ID

### tools/template_tools.py (45 LOC)
- `list_templates_impl()`: Lists available GNS3 templates

---

**Last Updated**: 2025-10-25
**Review Date**: 2026-04-25 (6 months)
