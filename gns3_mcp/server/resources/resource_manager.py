"""
Resource Manager for GNS3 MCP Server

Handles URI routing and resource retrieval for MCP resource protocol.
Routes resource URIs (ROUTES) to handler methods.
"""

import json
import re
from typing import TYPE_CHECKING, Dict, List, Tuple

from interfaces import IResourceManager

if TYPE_CHECKING:
    from interfaces import IAppContext


def _template_regex(template: str) -> str:
    """'nodes://{project_id}/{node_id}' -> anchored regex with named groups"""
    parts = re.split(r"\{(\w+)\}", template)
    # re.split with a group alternates literal, name, literal, ...
    body = "".join(
        re.escape(part) if i % 2 == 0 else f"(?P<{part}>[^/]+)" for i, part in enumerate(parts)
    )
    return f"^{body}$"


class ResourceManager(IResourceManager):
    """Manages MCP resources with URI routing"""

    # Single routing table for query_resource and its "supported_patterns" hint (GM-99:
    # a hand-kept copy drifted, so topology_report and diagrams were registered as MCP
    # resources but rejected by query_resource). Templates are spelled exactly like the
    # @mcp.resource URIs in main.py; tests/unit/test_resource_uris.py keeps them in sync.
    # Order matters where templates overlap: literal paths before {param} ones.
    ROUTES: List[Tuple[str, str]] = [
        ("projects://", "list_projects"),
        ("projects://{project_id}", "get_project"),
        ("projects://{project_id}/readme", "get_project_readme"),
        ("projects://{project_id}/topology_report", "get_topology_report"),
        ("projects://{project_id}/sessions/console/", "list_console_sessions"),
        ("projects://{project_id}/sessions/ssh/", "list_ssh_sessions"),
        ("nodes://{project_id}/", "list_nodes"),
        ("nodes://{project_id}/{node_id}", "get_node"),
        ("nodes://{project_id}/{node_id}/template", "get_node_template_usage"),
        ("links://{project_id}/", "list_links"),
        ("drawings://{project_id}/", "list_drawings"),
        ("templates://", "list_templates"),
        ("templates://{template_id}", "get_template"),
        # Session lists also take ?project_id=...
        ("sessions://console/", "list_console_sessions"),
        ("sessions://ssh/", "list_ssh_sessions"),
        ("sessions://console/{node_name}", "get_console_session"),
        ("sessions://ssh/{node_name}", "get_ssh_session"),
        ("sessions://ssh/{node_name}/history", "get_ssh_history"),
        ("sessions://ssh/{node_name}/buffer", "get_ssh_buffer"),
        ("proxies:///status", "get_proxy_status"),
        ("proxies://", "get_proxy_registry"),
        ("proxies://sessions", "list_proxy_sessions"),
        ("proxies://project/{project_id}", "list_project_proxies"),
        ("proxies://{proxy_id}", "get_proxy"),
        ("diagrams://{project_id}/topology", "get_topology_diagram"),
    ]

    # Query-parameter forms, listed in the error hint only
    QUERY_FORMS = [
        "sessions://console/?project_id={project_id}",
        "sessions://ssh/?project_id={project_id}",
    ]

    URI_PATTERNS = {_template_regex(template): handler for template, handler in ROUTES}

    def __init__(self, app: "IAppContext"):
        self.app = app

    def parse_uri(self, uri: str) -> tuple[str | None, Dict[str, str] | None]:
        """
        Parse resource URI and extract handler name and parameters

        Supports both path parameters and query parameters.

        Args:
            uri: Resource URI (e.g., nodes://abc123/ or sessions://console/?project_id=abc)

        Returns:
            Tuple of (handler_name, parameters_dict) or (None, None) if no match
        """
        # Split URI into base and query string
        if "?" in uri:
            base_uri, query_string = uri.split("?", 1)
            # Parse query parameters
            query_params = {}
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    query_params[key] = value
        else:
            base_uri = uri
            query_params = {}

        # Match base URI against patterns
        for pattern, handler in self.URI_PATTERNS.items():
            match = re.match(pattern, base_uri)
            if match:
                # Combine path parameters and query parameters
                params = match.groupdict()
                params.update(query_params)
                return handler, params

        return None, None

    async def get_resource(self, uri: str) -> str:
        """
        Get resource by URI

        Args:
            uri: Resource URI

        Returns:
            JSON string with resource data or error
        """
        handler_name, params = self.parse_uri(uri)

        if not handler_name:
            return json.dumps(
                {
                    "error": "Invalid resource URI",
                    "uri": uri,
                    "supported_patterns": [t for t, _ in self.ROUTES] + self.QUERY_FORMS,
                },
                indent=2,
            )

        # Call the appropriate handler method
        handler_method = getattr(self, handler_name, None)
        if not handler_method:
            return json.dumps(
                {"error": "Handler not implemented", "handler": handler_name, "uri": uri}, indent=2
            )

        try:
            return await handler_method(**params)
        except Exception as e:
            return json.dumps(
                {
                    "error": "Resource retrieval failed",
                    "handler": handler_name,
                    "uri": uri,
                    "details": str(e),
                },
                indent=2,
            )

    # ========================================================================
    # Project Resource Handlers
    # ========================================================================

    async def list_projects(self) -> str:
        """List all GNS3 projects with their statuses and IDs"""
        from .project_resources import list_projects_impl

        return await list_projects_impl(self.app)

    async def get_project(self, project_id: str) -> str:
        """Get project details"""
        from .project_resources import get_project_impl

        return await get_project_impl(self.app, project_id)

    async def list_nodes(self, project_id: str) -> str:
        """List nodes in project"""
        from .project_resources import list_nodes_impl

        return await list_nodes_impl(self.app, project_id)

    async def get_node(self, project_id: str, node_id: str) -> str:
        """Get node details"""
        from .project_resources import get_node_impl

        return await get_node_impl(self.app, project_id, node_id)

    async def list_links(self, project_id: str) -> str:
        """List links in project"""
        from .project_resources import list_links_impl

        return await list_links_impl(self.app, project_id)

    async def list_templates(self) -> str:
        """List available templates"""
        from .project_resources import list_templates_impl

        return await list_templates_impl(self.app)

    async def list_drawings(self, project_id: str) -> str:
        """List drawings in project"""
        from .project_resources import list_drawings_impl

        return await list_drawings_impl(self.app, project_id)

    # REMOVED v0.29.0 - Snapshot functionality removed (planned for future reimplementation)
    # async def list_snapshots(self, project_id: str) -> str:
    #     """List snapshots in project"""
    #     from .project_resources import list_snapshots_impl
    #     return await list_snapshots_impl(self.app, project_id)
    #
    # async def get_snapshot(self, project_id: str, snapshot_id: str) -> str:
    #     """Get snapshot details"""
    #     from .project_resources import get_snapshot_impl
    #     return await get_snapshot_impl(self.app, project_id, snapshot_id)

    async def get_project_readme(self, project_id: str) -> str:
        """Get project README/notes"""
        from .project_resources import get_project_readme_impl

        return await get_project_readme_impl(self.app, project_id)

    async def get_topology_report(self, project_id: str) -> str:
        """Get unified topology report with nodes, links, and statistics (v0.40.0)"""
        from .project_resources import get_topology_report_impl

        return await get_topology_report_impl(self.app, project_id)

    async def get_topology_diagram(self, project_id: str) -> str:
        """SVG topology diagram (diagrams://{project_id}/topology)"""
        from export_tools import generate_topology_diagram_content

        content, _mime_type = await generate_topology_diagram_content(
            self.app, project_id, format="svg", dpi=150
        )
        return content

    async def get_template(self, template_id: str) -> str:
        """Get template details with usage notes"""
        from .project_resources import get_template_impl

        return await get_template_impl(self.app, template_id)

    async def get_node_template_usage(self, project_id: str, node_id: str) -> str:
        """Get template usage notes for a specific node"""
        from .project_resources import get_node_template_usage_impl

        return await get_node_template_usage_impl(self.app, project_id, node_id)

    # ========================================================================
    # Session Resource Handlers
    # ========================================================================

    async def list_console_sessions(self, project_id: str | None = None) -> str:
        """List all active console sessions (optionally filtered by project_id)"""
        from .session_resources import list_console_sessions_impl

        return await list_console_sessions_impl(self.app, project_id)

    async def get_console_session(self, node_name: str) -> str:
        """Get console session status"""
        from .session_resources import get_console_session_impl

        return await get_console_session_impl(self.app, node_name)

    async def list_ssh_sessions(self, project_id: str | None = None) -> str:
        """List all active SSH sessions (optionally filtered by project_id)"""
        from .session_resources import list_ssh_sessions_impl

        return await list_ssh_sessions_impl(self.app, project_id)

    async def get_ssh_session(self, node_name: str) -> str:
        """Get SSH session status"""
        from .session_resources import get_ssh_session_impl

        return await get_ssh_session_impl(self.app, node_name)

    async def get_ssh_history(self, node_name: str) -> str:
        """Get SSH command history"""
        from .session_resources import get_ssh_history_impl

        return await get_ssh_history_impl(self.app, node_name)

    async def get_ssh_buffer(self, node_name: str) -> str:
        """Get SSH continuous buffer"""
        from .session_resources import get_ssh_buffer_impl

        return await get_ssh_buffer_impl(self.app, node_name)

    async def get_proxy_status(self) -> str:
        """Get SSH proxy service status"""
        from .session_resources import get_proxy_status_impl

        return await get_proxy_status_impl(self.app)

    async def get_proxy_registry(self) -> str:
        """Get proxy registry (discovered lab proxies)"""
        from .session_resources import get_proxy_registry_impl

        return await get_proxy_registry_impl(self.app)

    async def list_proxy_sessions(self) -> str:
        """List all SSH proxy sessions"""
        from .session_resources import list_proxy_sessions_impl

        return await list_proxy_sessions_impl(self.app)

    async def list_project_proxies(self, project_id: str) -> str:
        """List proxies for specific project (template-style)"""
        from .session_resources import list_project_proxies_impl

        return await list_project_proxies_impl(self.app, project_id)

    async def get_proxy(self, proxy_id: str) -> str:
        """Get specific proxy details by proxy_id"""
        from .session_resources import get_proxy_impl

        return await get_proxy_impl(self.app, proxy_id)
