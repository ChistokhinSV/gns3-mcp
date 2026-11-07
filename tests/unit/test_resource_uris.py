"""Every resource URI a client can see must work with query_resource (GM-99)

main.py registers MCP resources with @mcp.resource, query_resource routes through
ResourceManager.ROUTES. The two drifted: instructions told clients to query
projects://<id>/topology_report, which query_resource rejected. These tests tie the
routing table to the registered resources and to every URI in client-facing text.
"""

import ast
import re
from pathlib import Path

import pytest
from resources.resource_manager import ResourceManager

from .test_client_texts import _docstring_nodes, _is_mcp_registered

SERVER = Path(__file__).resolve().parents[2] / "gns3_mcp" / "server"
SKILL = SERVER.parents[1] / "plugin" / "skills" / "gns3-lab-automation"

ROUTE_TEMPLATES = [template for template, _ in ResourceManager.ROUTES]

# gns3:// and topology:// never existed as resource schemes; catch them in texts too
URI_IN_TEXT = re.compile(
    r"\b(?:projects|nodes|links|drawings|templates|sessions|proxies|diagrams|topology|gns3)"
    r"://[^\s`\"'),*\]]*"
)
PLACEHOLDER = re.compile(r"\{\{?[\w.]+\}?\}|<\w+>")


def _registered_resource_uris() -> list[str]:
    tree = ast.parse((SERVER / "main.py").read_text(encoding="utf-8"))
    uris = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == "resource"
            ):
                uris.append(dec.args[0].value)
    return uris


def _routes(uri: str) -> str | None:
    """Handler name query_resource would call for this URI (placeholders filled)"""
    concrete = PLACEHOLDER.sub("abc-123", uri.rstrip(".:;"))
    if concrete.startswith("gns3://"):
        # "gns3://projects://" = MCP resource URI prefix used by some clients
        concrete = concrete[len("gns3://") :]
    handler, _ = ResourceManager(app=None).parse_uri(concrete)
    if handler and hasattr(ResourceManager, handler):
        return handler
    return None


def test_every_route_has_a_handler():
    missing = [h for _, h in ResourceManager.ROUTES if not hasattr(ResourceManager, h)]
    assert missing == []


def test_every_registered_resource_is_routed():
    registered = _registered_resource_uris()
    assert len(registered) >= 20
    assert sorted(set(registered) - set(ROUTE_TEMPLATES)) == []


def test_every_route_is_a_registered_resource():
    assert sorted(set(ROUTE_TEMPLATES) - set(_registered_resource_uris())) == []


@pytest.mark.parametrize(
    "uri,handler",
    [
        ("projects://p-1/topology_report", "get_topology_report"),
        ("diagrams://p-1/topology", "get_topology_diagram"),
        ("proxies://sessions", "list_proxy_sessions"),
        ("proxies://px-1", "get_proxy"),
        ("proxies:///status", "get_proxy_status"),
        ("sessions://ssh/R1/history", "get_ssh_history"),
    ],
)
def test_parse_uri(uri, handler):
    assert ResourceManager(app=None).parse_uri(uri)[0] == handler


def test_query_params_are_passed():
    handler, params = ResourceManager(app=None).parse_uri("sessions://console/?project_id=p-1")
    assert (handler, params) == ("list_console_sessions", {"project_id": "p-1"})


@pytest.mark.asyncio
async def test_invalid_uri_lists_every_route():
    import json

    result = json.loads(await ResourceManager(app=None).get_resource("projects://p-1/bogus"))
    assert result["error"] == "Invalid resource URI"
    assert "projects://{project_id}/topology_report" in result["supported_patterns"]
    assert set(ROUTE_TEMPLATES) <= set(result["supported_patterns"])


def _code_texts(path: Path) -> list[str]:
    """String literals (f-strings whole, fields as {x}) and MCP-registered docstrings"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_nodes(tree)
    texts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(value.value)
                    skip.add(id(value))
                else:
                    parts.append("{x}")
            texts.append("".join(parts))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            texts.append(node.value)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _is_mcp_registered(node):
            texts.append(ast.get_docstring(node) or "")
    return texts


def _client_texts() -> list[tuple[str, str]]:
    """(source, text) for docs and for every string literal in the server code"""
    texts = [
        ("instructions.md", (SERVER / "instructions.md").read_text(encoding="utf-8")),
        ("SKILL.md", (SKILL / "SKILL.md").read_text(encoding="utf-8")),
    ]
    texts += [
        (ref.name, ref.read_text(encoding="utf-8")) for ref in (SKILL / "references").glob("*.md")
    ]
    for path in sorted(SERVER.rglob("*.py")):
        texts += [(str(path.relative_to(SERVER)), text) for text in _code_texts(path)]
    return texts


def test_uris_in_client_texts_are_routed():
    bad = sorted(
        {
            (source, match.group(0))
            for source, text in _client_texts()
            for match in URI_IN_TEXT.finditer(text)
            if not _routes(match.group(0))
        }
    )
    assert bad == []
