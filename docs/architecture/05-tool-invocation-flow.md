# Tool Invocation Data Flow

**Document Version**: 1.0
**Last Updated**: 2025-10-25

## Overview

This document describes the complete data flow when Claude invokes a GNS3 MCP tool, from user request to response delivery.

## End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Interaction (Natural Language)                     │
└──────────────────┬──────────────────────────────────────────┘
                   │ "List all routers in my lab"
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Claude AI (Desktop/Code)                                 │
│  - Understand intent                                        │
│  - Select appropriate tool: list_nodes()                    │
│  - Construct MCP request                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │ JSON-RPC Request
                   │ {"method": "tools/call",
                   │  "params": {"name": "list_nodes"}}
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. MCP Transport Layer                                      │
│  - stdio (Claude Desktop)                                   │
│  - SSE (Claude Code)                                        │
└──────────────────┬──────────────────────────────────────────┘
                   │ Serialized JSON-RPC
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. FastMCP Framework                                        │
│  - Deserialize request                                      │
│  - Validate JSON-RPC format                                 │
│  - Route to tool by name                                    │
│  - Inject Context (ctx)                                     │
└──────────────────┬──────────────────────────────────────────┘
                   │ Call @mcp.tool() function
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Tool Decorator (main.py)                                 │
│  @mcp.tool()                                                │
│  async def list_nodes(ctx: Context) -> str:                 │
│      app: AppContext = ctx.request_context.lifespan_context │
│      error = await validate_current_project(app)            │
│      if error: return error                                 │
│      return await list_nodes_impl(app)                      │
└──────────────────┬──────────────────────────────────────────┘
                   │ Delegate to implementation
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Tool Implementation (tools/node_tools.py)                │
│  async def list_nodes_impl(app: AppContext) -> str:         │
│      nodes = await app.gns3.get_nodes(app.current_project_id)│
│      node_models = [NodeInfo(...) for n in nodes]           │
│      return json.dumps([n.model_dump() for n in node_models])│
└──────────────────┬──────────────────────────────────────────┘
                   │ Call GNS3 API
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. GNS3 Client (gns3_client.py)                             │
│  async def get_nodes(self, project_id: str) -> List[Dict]:  │
│      headers = {"Authorization": f"Bearer {self.token}"}    │
│      response = await self.client.get(                      │
│          f"/v3/projects/{project_id}/nodes",                │
│          headers=headers                                    │
│      )                                                       │
│      return response.json()                                 │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP Request
                   │ GET /v3/projects/{id}/nodes
                   │ Authorization: Bearer <JWT>
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. GNS3 Server (External System)                            │
│  - Authenticate JWT                                         │
│  - Fetch nodes from database                                │
│  - Return JSON response                                     │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP 200 OK
                   │ [{node_id, name, status, console, ...}]
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Pydantic Model Validation (models.py)                    │
│  NodeInfo(                                                   │
│      node_id=n['node_id'],                                  │
│      name=n['name'],                                        │
│      status=n['status'],  # Validated: "started"/"stopped"  │
│      console=n.get('console'),                              │
│      console_type=n.get('console_type'),                    │
│      ...                                                     │
│  )                                                           │
└──────────────────┬──────────────────────────────────────────┘
                   │ Type-safe models
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. JSON Serialization                                       │
│  json.dumps([model.model_dump() for model in node_models],  │
│             indent=2)                                        │
└──────────────────┬──────────────────────────────────────────┘
                   │ JSON string
                   │ [{"node_id": "...", "name": "R1", ...}]
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 11. MCP Response                                             │
│  FastMCP serializes result into JSON-RPC response:          │
│  {                                                           │
│    "jsonrpc": "2.0",                                         │
│    "id": 1,                                                  │
│    "result": {                                               │
│      "content": [{"type": "text", "text": "[{...}]"}]       │
│    }                                                         │
│  }                                                           │
└──────────────────┬──────────────────────────────────────────┘
                   │ JSON-RPC over stdio/SSE
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 12. Claude AI (Process Response)                            │
│  - Parse JSON data                                          │
│  - Format for user display                                  │
│  - Extract relevant information                             │
└──────────────────┬──────────────────────────────────────────┘
                   │ Natural language response
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 13. User sees result                                        │
│  "Your lab has 3 routers:                                   │
│   - R1 (stopped)                                            │
│   - R2 (started, console port 5001)                         │
│   - R3 (started, console port 5002)"                        │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Flow Breakdown

### Phase 1: Request Initiation

**User → Claude AI**:
- User types natural language request
- Claude's reasoning engine selects appropriate tool
- Generates structured tool call

**Example**:
```
User: "Show me all the devices in my network lab"
Claude thinks: This requires listing nodes in the current project
             ↓
Tool Selection: list_nodes()
```

### Phase 2: MCP Protocol Handling

**Claude → MCP Server**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "list_nodes",
    "arguments": {}
  }
}
```

**Transport**:
- **Claude Desktop**: stdio pipes (stdin/stdout)
- **Claude Code**: Server-Sent Events (HTTP)

### Phase 3: Server-Side Processing

**FastMCP Framework**:
1. Receives JSON-RPC request
2. Validates protocol format
3. Routes to registered tool by name
4. Injects `Context` object
5. Calls tool function

**Context Object**:
```python
ctx: Context
    ├─ request_context
    │   └─ lifespan_context: AppContext
    │       ├─ gns3: GNS3Client
    │       ├─ console: ConsoleManager
    │       └─ current_project_id: Optional[str]
```

### Phase 4: Tool Execution

**Tool Decorator (main.py)**:
```python
@mcp.tool()
async def list_nodes(ctx: Context) -> str:
    # Step 1: Extract application context
    app: AppContext = ctx.request_context.lifespan_context

    # Step 2: Validate preconditions
    error = await validate_current_project(app)
    if error:
        return error  # Early return with error message

    # Step 3: Delegate to implementation
    return await list_nodes_impl(app)
```

**Validation Example**:
```python
async def validate_current_project(app: AppContext) -> Optional[str]:
    if not app.current_project_id:
        return json.dumps(ErrorResponse(
            error="No project opened",
            details="Use open_project() first to select a project.",
            suggested_action="Call open_project(\"My Lab\")"
        ).model_dump(), indent=2)
    return None
```

### Phase 5: Business Logic

**Tool Implementation (tools/node_tools.py)**:
```python
async def list_nodes_impl(app: "AppContext") -> str:
    try:
        # Step 1: Fetch raw data from GNS3 API
        nodes = await app.gns3.get_nodes(app.current_project_id)

        # Step 2: Validate and transform to Pydantic models
        node_models = [
            NodeInfo(
                node_id=n['node_id'],
                name=n['name'],
                status=n['status'],
                node_type=n.get('node_type'),
                console=n.get('console'),
                console_type=n.get('console_type'),
                x=n.get('x', 0),
                y=n.get('y', 0),
                z=n.get('z', 0),
                locked=n.get('locked', False)
            )
            for n in nodes
        ]

        # Step 3: Serialize to JSON
        return json.dumps([n.model_dump() for n in node_models], indent=2)

    except Exception as e:
        # Step 4: Handle errors gracefully
        return json.dumps(ErrorResponse(
            error="Failed to list nodes",
            details=str(e)
        ).model_dump(), indent=2)
```

### Phase 6: External API Call

**GNS3 Client (gns3_client.py)**:
```python
async def get_nodes(self, project_id: str) -> List[Dict]:
    # Step 1: Construct URL
    url = f"{self.base_url}/projects/{project_id}/nodes"

    # Step 2: Add authentication
    headers = {"Authorization": f"Bearer {self.token}"}

    # Step 3: Make async HTTP request
    response = await self.client.get(url, headers=headers)

    # Step 4: Handle HTTP errors
    if response.status_code != 200:
        error = self._extract_error(response)
        raise Exception(f"GNS3 API error: {error}")

    # Step 5: Return parsed JSON
    return response.json()
```

**HTTP Request**:
```http
GET /v3/projects/abc-123-def/nodes HTTP/1.1
Host: 192.168.1.20:80
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
```

**HTTP Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

[
  {
    "node_id": "node-1",
    "name": "R1",
    "status": "stopped",
    "node_type": "qemu",
    "console": 5001,
    "console_type": "telnet",
    "x": 100,
    "y": 200,
    "z": 0
  },
  ...
]
```

### Phase 7: Data Validation

**Pydantic Model Validation**:
```python
# models.py
class NodeInfo(BaseModel):
    node_id: str
    name: str
    status: Literal["started", "stopped", "suspended"]  # ✅ Validates enum
    node_type: Optional[str]
    console: Optional[int] = Field(None, ge=1, le=65535)  # ✅ Validates port range
    console_type: Optional[str]
    x: int = 0
    y: int = 0
    z: int = 0
    locked: bool = False

# Validation happens here:
NodeInfo(**node_dict)  # ✅ Raises ValidationError if invalid
```

### Phase 8: Response Serialization

**JSON Output**:
```json
[
  {
    "node_id": "node-1",
    "name": "R1",
    "status": "stopped",
    "node_type": "qemu",
    "console": 5001,
    "console_type": "telnet",
    "x": 100,
    "y": 200,
    "z": 0,
    "locked": false
  }
]
```

**MCP Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"node_id\": \"node-1\", ...}]"
      }
    ]
  }
}
```

### Phase 9: Claude Processing

Claude AI receives JSON response:
1. Parses JSON data
2. Understands structure
3. Formats for human readability
4. Generates natural language response

**Output to User**:
```
I found 3 devices in your lab:

1. **R1** (Router)
   - Status: Stopped
   - Console: Port 5001 (telnet)

2. **R2** (Router)
   - Status: Started
   - Console: Port 5002 (telnet)

3. **SW1** (Switch)
   - Status: Started
   - No console configured
```

## Error Handling Flow

### Scenario: Project Not Opened

```
User Request: "List all nodes"
    ↓
list_nodes(ctx)
    ↓
validate_current_project(app)
    ↓
app.current_project_id is None  # ❌ Validation fails
    ↓
Return ErrorResponse:
{
  "error": "No project opened",
  "details": "Use open_project() first to select a project.",
  "suggested_action": "Call open_project(\"My Lab\")"
}
    ↓
Claude receives error
    ↓
User sees: "You need to open a project first. Try: open_project(\"My Lab\")"
```

### Scenario: GNS3 API Error

```
list_nodes_impl(app)
    ↓
app.gns3.get_nodes(project_id)
    ↓
HTTP Request to GNS3 Server
    ↓
HTTP 404 Not Found  # ❌ Project doesn't exist
    ↓
gns3_client raises Exception
    ↓
try/except catches exception
    ↓
Return ErrorResponse:
{
  "error": "Failed to list nodes",
  "details": "Project not found: abc-123"
}
    ↓
User sees: "Error: Project not found. Please check the project ID."
```

## Performance Characteristics

**Typical Latency Breakdown** (local GNS3):

| Phase | Component | Time | Percentage |
|-------|-----------|------|------------|
| 1-2 | User → Claude (reasoning) | ~500ms | 40% |
| 3-4 | MCP protocol overhead | ~5ms | 0.4% |
| 5 | Tool validation | ~1ms | 0.1% |
| 6 | GNS3 API call | ~10ms | 0.8% |
| 7 | Pydantic validation | ~2ms | 0.2% |
| 8-9 | JSON serialization | ~1ms | 0.1% |
| 10-11 | Response to Claude | ~5ms | 0.4% |
| 12 | Claude formatting | ~700ms | 56% |
| **Total** | | **~1,224ms** | **100%** |

**Key Insights**:
- AI reasoning dominates latency (96%)
- MCP server execution is fast (<20ms)
- Network I/O to GNS3 minimal for local deployments
- Type validation overhead negligible (<2ms)

## Concurrency and Async Flow

**Async Execution**:
```python
# Multiple tools can execute concurrently
await asyncio.gather(
    list_nodes_impl(app),
    get_links_impl(app),
    list_drawings_impl(app)
)
```

**Background Tasks**:
```python
# Console manager runs background reader tasks
reader_task = asyncio.create_task(_console_reader_loop(session))

# Periodic cleanup task
cleanup_task = asyncio.create_task(_periodic_cleanup(console_manager))
```

## Related Documentation

- [02-c4-container-diagram.puml](02-c4-container-diagram.puml) - Container architecture
- [06-console-buffering-flow.md](06-console-buffering-flow.md) - Console-specific flow
- [components/gns3-client.md](components/gns3-client.md) - GNS3 API client details
- [components/data-models.md](components/data-models.md) - Pydantic model structure

---

**Document Version**: 1.0
**Last Updated**: 2025-10-25
**Next Review**: 2026-01-25
