"""
Resource Manager for GNS3 MCP Server

Handles URI routing and resource retrieval for MCP resource protocol.
Supports 15 resource URIs for browsable state.
"""

import json
import re
from typing import TYPE_CHECKING, Any, Dict, List

from interfaces import IResourceManager

if TYPE_CHECKING:
    from interfaces import IAppContext


class ResourceManager(IResourceManager):
    """Manages MCP resources with URI routing"""

    # URI patterns with named groups
    URI_PATTERNS = {
        # Project resources
        r"^projects://$": "list_projects",
        r"^projects://(?P<project_id>[^/]+)$": "get_project",
        r"^projects://(?P<project_id>[^/]+)/readme$": "get_project_readme",
        r"^projects://(?P<project_id>[^/]+)/sessions/console/$": "list_console_sessions",  # Project-scoped console sessions
        r"^projects://(?P<project_id>[^/]+)/sessions/ssh/$": "list_ssh_sessions",  # Project-scoped SSH sessions
        r"^nodes://(?P<project_id>[^/]+)/$": "list_nodes",
        r"^nodes://(?P<project_id>[^/]+)/(?P<node_id>[^/]+)$": "get_node",
        r"^nodes://(?P<project_id>[^/]+)/(?P<node_id>[^/]+)/template$": "get_node_template_usage",
        r"^links://(?P<project_id>[^/]+)/$": "list_links",
        r"^drawings://(?P<project_id>[^/]+)/$": "list_drawings",
        # Templates (static, not project-scoped)
        r"^templates://$": "list_templates",
        r"^templates://(?P<template_id>[^/]+)$": "get_template",
        # Session list resources (support query param: ?project_id=xxx)
        r"^sessions://console/$": "list_console_sessions",  # All or filtered by ?project_id
        r"^sessions://ssh/$": "list_ssh_sessions",  # All or filtered by ?project_id
        # Node-specific session resources (by node name, not project-scoped)
        r"^sessions://console/(?P<node_name>[^/]+)$": "get_console_session",
        r"^sessions://ssh/(?P<node_name>[^/]+)$": "get_ssh_session",
        r"^sessions://ssh/(?P<node_name>[^/]+)/history$": "get_ssh_history",
        r"^sessions://ssh/(?P<node_name>[^/]+)/buffer$": "get_ssh_buffer",
        # SSH proxy resources
        r"^proxies:///status$": "get_proxy_status",
        r"^proxies://$": "get_proxy_registry",
        r"^proxies://sessions$": "list_proxy_sessions",
        r"^proxies://project/(?P<project_id>[^/]+)$": "list_project_proxies",  # Path-based, not query param
        r"^proxies://(?P<proxy_id>[^/]+)$": "get_proxy",
    }

    def __init__(self, app: "IAppContext"):
        self.app = app

    def parse_uri(self, uri: str) -> tuple[str | None, Dict[str, str] | None]:
        """
        Parse resource URI and extract handler name and parameters

        Supports both path parameters and query parameters.

        Args:
            uri: Resource URI (e.g., projects://abc123/nodes/ or sessions://console/?project_id=abc)

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
                    "supported_patterns": [
                        "projects://",
                        "projects://{id}",
                        "projects://{id}/readme",
                        "projects://{id}/sessions/console/",
                        "projects://{id}/sessions/ssh/",
                        "nodes://{project_id}/",
                        "nodes://{project_id}/{node_id}",
                        "nodes://{project_id}/{node_id}/template",
                        "links://{project_id}/",
                        "drawings://{project_id}/",
                        "templates://",
                        "templates://{id}",
                        "sessions://console/",
                        "sessions://console/?project_id={id}",
                        "sessions://console/{node_name}",
                        "sessions://ssh/",
                        "sessions://ssh/?project_id={id}",
                        "sessions://ssh/{node_name}",
                        "sessions://ssh/{node_name}/history",
                        "sessions://ssh/{node_name}/buffer",
                        "proxies:///status",
                        "proxies://",
                        "proxies://sessions",
                        "proxies://project/{project_id}",
                        "proxies://{proxy_id}",
                    ],
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

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources

        Returns:
            List of resource metadata dicts
        """
        resources = []

        # Project resources
        projects = await self.app.gns3.get_projects()

        # Add projects list resource
        resources.append(
            {
                "uri": "projects://",
                "name": "Projects",
                "description": "List of all GNS3 projects",
                "mimeType": "application/json",
            }
        )

        # Add individual project resources
        for proj in projects:
            project_id = proj["project_id"]
            resources.extend(
                [
                    {
                        "uri": f"projects://{project_id}",
                        "name": f"Project: {proj['name']}",
                        "description": f"Details for project {proj['name']}",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": f"projects://{project_id}/nodes/",
                        "name": f"Nodes in {proj['name']}",
                        "description": f"List of nodes in project {proj['name']}",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": f"projects://{project_id}/links/",
                        "name": f"Links in {proj['name']}",
                        "description": f"List of links in project {proj['name']}",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": f"projects://{project_id}/templates/",
                        "name": f"Templates in {proj['name']}",
                        "description": f"Available templates for project {proj['name']}",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": f"projects://{project_id}/drawings/",
                        "name": f"Drawings in {proj['name']}",
                        "description": f"List of drawings in project {proj['name']}",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": f"projects://{project_id}/snapshots/",
                        "name": f"Snapshots in {proj['name']}",
                        "description": f"List of snapshots in project {proj['name']}",
                        "mimeType": "application/json",
                    },
                ]
            )

        # Session resources
        resources.extend(
            [
                {
                    "uri": "sessions://console/",
                    "name": "Console Sessions",
                    "description": "List of active console sessions",
                    "mimeType": "application/json",
                },
                {
                    "uri": "sessions://ssh/",
                    "name": "SSH Sessions",
                    "description": "List of active SSH sessions",
                    "mimeType": "application/json",
                },
                {
                    "uri": "proxies://status",
                    "name": "Main SSH Proxy Status",
                    "description": "Gets status of the main SSH proxy that resides on GNS3 host",
                    "mimeType": "application/json",
                },
                {
                    "uri": "proxies://sessions",
                    "name": "SSH Proxy Sessions",
                    "description": "All SSH proxy sessions",
                    "mimeType": "application/json",
                },
            ]
        )

        return resources

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
