"""Client-facing texts must name only tools that exist (GM-93)

Tools were consolidated in v0.47 (`set_node_properties` -> `node(action="set")`, ...), but
server instructions, prompts and error hints kept the old names for months, so clients
called tools that no longer exist. This scans everything a client can receive:

- instructions.md (sent on initialize)
- every prompt, rendered for each device/topology/issue branch
- docstrings of functions registered as MCP tools/resources/prompts (their descriptions)
- every other string literal in the server (error messages, suggestions, templates)
"""

import ast
import asyncio
import re
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[2] / "gns3_mcp" / "server"

REMOVED_TOOLS = [
    "set_node_properties",
    "set_node",
    "send_console_data",
    "read_console_output",
    "send_and_wait_console",
    "send_console",
    "read_console",
    "send_keystroke",
    "console_send_and_wait",
    "console_send",
    "console_read",
    "console_keystroke",
    "list_nodes",
    "list_projects",
    "open_project",
    "create_node",
    "delete_node",
    "set_connection",
    "set_network_connections",
    "get_links",
    "get_topology",
    "ssh_configure",
    "ssh_command",
    "ssh_disconnect",
    "configure_ssh_session",
    "execute_ssh_command",
    "disconnect_ssh_session",
    "get_project_readme",
    "update_project_readme",
    "create_snapshot",
    "list_templates",
    "get_console_status",
    "disconnect_console",
    "check_gns3_connection",
    "retry_gns3_connection",
    "create_drawing",
    "create_drawings_batch",
    "update_drawing",
    "delete_drawing",
    "get_node_file",
    "write_node_file",
    "configure_node_network",
    "console_batch_operations",
    "ssh_batch_operations",
    "get_node_details",
]

# A removed name used as a call: `send_console(` or `set_node(`
REMOVED_CALL = re.compile(r"\b(" + "|".join(REMOVED_TOOLS) + r")\(")


def _stale_calls(text: str) -> list[str]:
    return sorted(set(REMOVED_CALL.findall(text)))


def test_instructions():
    assert _stale_calls((SERVER / "instructions.md").read_text(encoding="utf-8")) == []


DEVICE_TYPES = ("cisco_ios", "linux", "mikrotik_routeros", "juniper_junos", "arista_eos", "other")

PROMPT_CASES = (
    [
        ("render_node_setup_prompt", ("R1", "Cisco IOSv", "10.0.0.1"), {"device_type": dt})
        for dt in DEVICE_TYPES
    ]
    + [("render_ssh_setup_prompt", ("R1", dt), {}) for dt in DEVICE_TYPES]
    + [
        ("render_lab_setup_prompt", (topo, 3), {})
        for topo in ("star", "mesh", "linear", "ring", "ospf", "bgp")
    ]
    + [("render_topology_discovery_prompt", ("Lab1", True), {})]
    + [
        ("render_troubleshooting_prompt", ("R1", issue), {})
        for issue in (None, "connectivity", "console", "ssh", "performance")
    ]
)


@pytest.mark.parametrize("func,args,kwargs", PROMPT_CASES, ids=lambda v: str(v))
def test_prompts_render_with_current_tools(func, args, kwargs):
    import prompts

    # Rendering itself is part of the test: the troubleshooting prompt used to raise ValueError
    rendered = getattr(prompts, func)(*args, **kwargs)
    if asyncio.iscoroutine(rendered):
        rendered = asyncio.run(rendered)
    assert _stale_calls(rendered) == []


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of docstring Constant nodes (module, class, function)"""
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _is_mcp_registered(func: ast.AST) -> bool:
    """@mcp.tool / @mcp.resource / @mcp.prompt - their docstrings become descriptions"""
    for dec in getattr(func, "decorator_list", []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr in {"tool", "resource", "prompt"}:
            return True
    return False


def _client_strings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    texts = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _is_mcp_registered(node):
            texts.append(ast.get_docstring(node) or "")
    return texts


@pytest.mark.parametrize(
    "path", sorted(SERVER.rglob("*.py")), ids=lambda p: str(p.relative_to(SERVER))
)
def test_string_literals_and_tool_descriptions(path):
    stale = sorted({hit for text in _client_strings(path) for hit in _stale_calls(text)})
    assert stale == [], f"{path.name}: {stale}"


def test_documented_prompt_names_are_registered():
    """Prompts are registered as "<Name> Workflow"; docs must use those names"""
    registered = set(
        re.findall(
            r'@mcp\.prompt\(\s*name="([^"]+)"', (SERVER / "main.py").read_text(encoding="utf-8")
        )
    )
    skill = SERVER.parents[1] / "plugin" / "skills" / "gns3-lab-automation"
    for doc in (
        SERVER / "instructions.md",
        skill / "SKILL.md",
        skill / "references" / "devices.md",
    ):
        mentioned = set(
            re.findall(r'"([A-Z][A-Za-z ]+ Workflow)"', doc.read_text(encoding="utf-8"))
        )
        assert mentioned, doc.name
        assert mentioned <= registered, (doc.name, mentioned - registered)
