# GNS3 MCP Server - Architecture Documentation

**Version**: v0.11.0
**Last Updated**: 2025-10-25
**Status**: ✅ Current

## Overview

This directory contains comprehensive architecture documentation for the GNS3 MCP Server, a Model Context Protocol server that provides programmatic access to GNS3 network simulation labs.

**Architecture Grade**: B+ (85/100)

## Documentation Structure

### 1. C4 Model Diagrams

The [C4 model](https://c4model.com/) provides a hierarchical set of software architecture diagrams:

- **[01-c4-context-diagram.puml](01-c4-context-diagram.puml)** - System context showing external actors and systems
- **[02-c4-container-diagram.puml](02-c4-container-diagram.puml)** - Internal containers (MCP server, tools, clients)
- **[03-c4-component-diagram.puml](03-c4-component-diagram.puml)** - Component details (tool modules, validators, managers)
- **[04-deployment-diagram.puml](04-deployment-diagram.puml)** - Deployment architecture (Claude Desktop/Code, GNS3 host)

**Viewing Diagrams**:
```bash
# Install PlantUML
npm install -g node-plantuml

# Generate PNG diagrams
plantuml docs/architecture/*.puml

# Or use online viewer
# https://www.plantuml.com/plantuml/uml/
```

### 2. Architecture Decision Records (ADRs)

ADRs document significant architectural decisions with context and rationale:

- **[ADR-001: Remove Caching Infrastructure](adr/ADR-001-remove-caching-infrastructure.md)** (v0.9.0 - Breaking)
  - Removed 274 LOC of caching for simpler, more predictable behavior
  - Rationale: <10ms local API latency made caching marginal

- **[ADR-003: Extract Tool Implementations](adr/ADR-003-extract-tool-implementations.md)** (v0.11.0 - Refactor)
  - Extracted 19 tools to 6 category modules
  - 50% LOC reduction in main.py (1,836 → 914 lines)
  - Improved testability and maintainability

- **[ADR-005: Two-Phase Link Validation](adr/ADR-005-two-phase-link-validation.md)** (v0.3.0 - Major Refactor)
  - Atomic topology changes with validate-all → execute-all pattern
  - Prevents partial topology corruption on batch operation failures

### 3. Data Flow Documentation

- **[05-tool-invocation-flow.md](05-tool-invocation-flow.md)** - Request/response flow through system layers
- **[06-console-buffering-flow.md](06-console-buffering-flow.md)** - Async telnet console output management
- **[07-two-phase-validation-flow.md](07-two-phase-validation-flow.md)** - Link topology validation algorithm

### 4. Component Documentation

- **[components/gns3-client.md](components/gns3-client.md)** - GNS3 v3 API client architecture
- **[components/console-manager.md](components/console-manager.md)** - Telnet session management
- **[components/link-validator.md](components/link-validator.md)** - Two-phase validation logic
- **[components/data-models.md](components/data-models.md)** - Pydantic model architecture

## Quick Start

### For New Developers

1. **Start with Context Diagram**: Understand external systems and boundaries
   - Read [01-c4-context-diagram.puml](01-c4-context-diagram.puml)

2. **Review Container Architecture**: Learn internal components
   - Read [02-c4-container-diagram.puml](02-c4-container-diagram.puml)

3. **Understand Tool Organization**: See how tools are structured
   - Read [ADR-003: Extract Tool Implementations](adr/ADR-003-extract-tool-implementations.md)

4. **Explore Data Flow**: Follow a request through the system
   - Read [05-tool-invocation-flow.md](05-tool-invocation-flow.md)

### For Architects

1. **Review ADRs**: Understand key architectural decisions
   - Start with [ADR-001](adr/ADR-001-remove-caching-infrastructure.md), [ADR-003](adr/ADR-003-extract-tool-implementations.md), [ADR-005](adr/ADR-005-two-phase-link-validation.md)

2. **Analyze Patterns**: Identify architectural patterns in use
   - Repository Pattern (gns3_client)
   - Session Manager Pattern (console_manager)
   - Two-Phase Validation (link_validator)
   - Context Object Pattern (AppContext)

3. **Review Compliance**: Check SOLID principles and best practices
   - See ADR appendices for compliance analysis

## Architecture Highlights

### Strengths

- ✅ **Clean Layered Architecture**: Presentation → Business → Integration layers with strict boundaries
- ✅ **Type Safety**: Pydantic v2 models with runtime validation for all data structures
- ✅ **Modular Design**: 6 category-based tool modules with zero circular dependencies
- ✅ **Comprehensive Testing**: 134 unit tests with 30%+ coverage on critical paths
- ✅ **Atomic Operations**: Two-phase validation prevents partial topology changes
- ✅ **Well-Documented**: 100% docstring coverage, ADRs, migration guides

### Improvements Recommended

- ⚠️ Integration testing for end-to-end workflows
- ⚠️ Error recovery and resilience patterns
- ⚠️ Type checking enforcement in CI (mypy)
- ⚠️ Interface abstraction for dependency inversion

## Key Metrics

**Codebase**:
- Production: 2,899 LOC (server/)
- Tests: 2,559 LOC (134 tests)
- Test/Code Ratio: 0.88 (excellent)
- Type Hints Coverage: 95%+
- Documentation Coverage: 100%

**Performance**:
- API Call Latency: <10ms (local GNS3)
- Console Connect: ~100-300ms (telnet handshake)
- SVG Export: ~50-100ms (100 nodes)
- PNG Export: ~200-500ms (CairoSVG)

**Test Coverage** (v0.11.0):
- models.py: 100% (41 tests)
- link_validator.py: 96% (37 tests)
- console_manager.py: 76% (38 tests)
- gns3_client.py: 75% (30 tests)
- Overall: ~30% (focused on critical paths)

## Architectural Patterns

### Repository Pattern (gns3_client.py)

Abstracts GNS3 v3 API interactions with async interface:
```python
class GNS3Client:
    async def get_projects() -> List[Dict]
    async def create_link(project_id, spec) -> Dict
    # 20+ methods wrapping REST endpoints
```

**Benefits**: Centralizes error handling, hides JWT auth, enables easy mocking

### Session Manager Pattern (console_manager.py)

Manages concurrent telnet connections with background reading:
```python
class ConsoleManager:
    sessions: Dict[str, ConsoleSession]
    async def connect(host, port, node_name) -> str
    async def send(session_id, data) -> bool
    def get_diff(session_id) -> Optional[str]  # Incremental reads
```

**Features**: Auto-connect, background tasks, 30-min timeout, diff tracking

### Two-Phase Validation (link_validator.py)

Atomic topology changes with validate-all → execute-all:
```python
# Phase 1: Validate ALL (no API calls)
for op in operations:
    error = validator.validate_connect(...)
    if error: return error_response

# Phase 2: Execute ALL (only if all valid)
for op in operations:
    await gns3.create_link(...)
```

**Benefits**: Prevents partial topology changes, clear error reporting

### Context Object Pattern (AppContext)

Dependency injection with lifecycle management:
```python
@dataclass
class AppContext:
    gns3: GNS3Client
    console: ConsoleManager
    current_project_id: Optional[str]

@asynccontextmanager
async def app_lifespan() -> AsyncIterator[AppContext]:
    context = AppContext(...)
    try:
        yield context
    finally:
        await cleanup()
```

**Benefits**: Automatic resource cleanup, shared state, lifecycle hooks

## Technology Stack

### Runtime Dependencies

```
mcp>=1.2.1            # MCP protocol (Anthropic official)
httpx>=0.28.1         # Async HTTP client for GNS3 API
telnetlib3>=2.0.4     # Async telnet client (vs deprecated telnetlib)
pydantic>=2.0.0       # Type-safe data models
python-dotenv>=1.1.1  # Environment variable loading
cairosvg>=2.7.0       # SVG → PNG (cross-platform, no Qt)
```

### Testing Dependencies

```
pytest>=8.4.2         # Test framework
pytest-asyncio>=1.2.0 # Async test support
pytest-mock>=3.15.1   # Mocking utilities
pytest-cov>=7.0.0     # Coverage reporting
```

## Integration Points

### GNS3 v3 API

- **Protocol**: REST over HTTP
- **Auth**: JWT Bearer tokens (24h expiry)
- **Base URL**: `http://{host}:{port}/v3/`
- **Key Endpoints**:
  - POST /v3/access/users/authenticate
  - GET /v3/projects, /v3/projects/{id}/nodes
  - POST /v3/projects/{id}/links
  - GET /v3/templates

### Telnet Console

- **Protocol**: Telnet (RFC 854)
- **Library**: telnetlib3 (async)
- **Connection**: `{gns3_host}:{node.console_port}`
- **Features**: ANSI stripping, line normalization, background buffering

### MCP Protocol

- **Framework**: FastMCP (Anthropic official)
- **Transport**: stdio (Claude Desktop), SSE (Claude Code)
- **Format**: JSON-RPC 2.0
- **Lifecycle**: app_lifespan() manages setup/cleanup

## Development Roadmap

### v0.12.0 (Next Release)

- [ ] Integration test suite with Docker-based GNS3
- [ ] Add mypy type checking to CI
- [ ] Category-specific test modules (test_node_tools.py, etc.)
- [ ] Extract shared validation helpers

### v1.0.0 (Future)

- [ ] VNC console support
- [ ] SSH console support
- [ ] Interface abstraction (Protocol classes)
- [ ] Metrics and observability
- [ ] Performance benchmarking suite

## Contributing

### Adding New Tools

1. Create implementation in `tools/{category}_tools.py`
2. Define Pydantic models (if needed)
3. Add `@mcp.tool()` decorator in `main.py`
4. Update `manifest.json`
5. Write unit tests
6. Update SKILL.md with examples

### Creating ADRs

Follow the ADR template:
1. Status (Proposed/Accepted/Deprecated)
2. Context and Problem Statement
3. Decision Drivers
4. Considered Options
5. Decision Outcome
6. Consequences (Positive/Negative/Neutral)
7. Validation and Compliance

## References

- **MCP Documentation**: https://modelcontextprotocol.io/
- **GNS3 API Reference**: https://apiv3.gns3.net/
- **C4 Model**: https://c4model.com/
- **PlantUML**: https://plantuml.com/
- **ADR Guidelines**: https://adr.github.io/

## Questions?

- **Architecture issues**: File issue with `architecture` label
- **ADR questions**: Review [ADR template](adr/ADR-TEMPLATE.md)
- **Diagram updates**: Edit .puml files, regenerate with PlantUML

---

**Maintained By**: Architecture Team
**Review Cycle**: Quarterly (January, April, July, October)
**Next Review**: 2026-01-25
