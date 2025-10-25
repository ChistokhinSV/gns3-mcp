"""
Resource Manager for GNS3 MCP Server

Handles URI routing and resource retrieval for MCP resource protocol.
Supports 15 resource URIs for browsable state.
"""

import json
import re
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from main import AppContext


class ResourceManager:
    """Manages MCP resources with URI routing"""

    # URI patterns with named groups
    URI_PATTERNS = {
        # Project resources
        r'^gns3://projects/$': 'list_projects',
        r'^gns3://projects/(?P<project_id>[^/]+)$': 'get_project',
        r'^gns3://projects/(?P<project_id>[^/]+)/nodes/$': 'list_nodes',
        r'^gns3://projects/(?P<project_id>[^/]+)/nodes/(?P<node_id>[^/]+)$': 'get_node',
        r'^gns3://projects/(?P<project_id>[^/]+)/links/$': 'list_links',
        r'^gns3://projects/(?P<project_id>[^/]+)/templates/$': 'list_templates',
        r'^gns3://projects/(?P<project_id>[^/]+)/drawings/$': 'list_drawings',
        r'^gns3://projects/(?P<project_id>[^/]+)/snapshots/$': 'list_snapshots',
        r'^gns3://projects/(?P<project_id>[^/]+)/snapshots/(?P<snapshot_id>[^/]+)$': 'get_snapshot',

        # Console session resources
        r'^gns3://sessions/console/$': 'list_console_sessions',
        r'^gns3://sessions/console/(?P<node_name>[^/]+)$': 'get_console_session',

        # SSH session resources
        r'^gns3://sessions/ssh/$': 'list_ssh_sessions',
        r'^gns3://sessions/ssh/(?P<node_name>[^/]+)$': 'get_ssh_session',
        r'^gns3://sessions/ssh/(?P<node_name>[^/]+)/history$': 'get_ssh_history',
        r'^gns3://sessions/ssh/(?P<node_name>[^/]+)/buffer$': 'get_ssh_buffer',

        # SSH proxy resources
        r'^gns3://proxy/status$': 'get_proxy_status',
        r'^gns3://proxy/sessions$': 'list_proxy_sessions',
    }

    def __init__(self, app: "AppContext"):
        self.app = app

    def parse_uri(self, uri: str) -> tuple[Optional[str], Optional[Dict[str, str]]]:
        """
        Parse resource URI and extract handler name and parameters

        Args:
            uri: Resource URI (e.g., gns3://projects/abc123/nodes/)

        Returns:
            Tuple of (handler_name, parameters_dict) or (None, None) if no match
        """
        for pattern, handler in self.URI_PATTERNS.items():
            match = re.match(pattern, uri)
            if match:
                return handler, match.groupdict()

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
            return json.dumps({
                "error": "Invalid resource URI",
                "uri": uri,
                "supported_patterns": [
                    "gns3://projects/",
                    "gns3://projects/{id}",
                    "gns3://projects/{id}/nodes/",
                    "gns3://projects/{id}/nodes/{id}",
                    "gns3://projects/{id}/links/",
                    "gns3://projects/{id}/templates/",
                    "gns3://projects/{id}/drawings/",
                    "gns3://projects/{id}/snapshots/",
                    "gns3://projects/{id}/snapshots/{id}",
                    "gns3://sessions/console/",
                    "gns3://sessions/console/{node}",
                    "gns3://sessions/ssh/",
                    "gns3://sessions/ssh/{node}",
                    "gns3://sessions/ssh/{node}/history",
                    "gns3://sessions/ssh/{node}/buffer",
                    "gns3://proxy/status",
                    "gns3://proxy/sessions",
                ]
            }, indent=2)

        # Call the appropriate handler method
        handler_method = getattr(self, handler_name, None)
        if not handler_method:
            return json.dumps({
                "error": "Handler not implemented",
                "handler": handler_name,
                "uri": uri
            }, indent=2)

        try:
            return await handler_method(**params)
        except Exception as e:
            return json.dumps({
                "error": "Resource retrieval failed",
                "handler": handler_name,
                "uri": uri,
                "details": str(e)
            }, indent=2)

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
        resources.append({
            "uri": "gns3://projects/",
            "name": "Projects",
            "description": "List of all GNS3 projects",
            "mimeType": "application/json"
        })

        # Add individual project resources
        for proj in projects:
            project_id = proj['project_id']
            resources.extend([
                {
                    "uri": f"gns3://projects/{project_id}",
                    "name": f"Project: {proj['name']}",
                    "description": f"Details for project {proj['name']}",
                    "mimeType": "application/json"
                },
                {
                    "uri": f"gns3://projects/{project_id}/nodes/",
                    "name": f"Nodes in {proj['name']}",
                    "description": f"List of nodes in project {proj['name']}",
                    "mimeType": "application/json"
                },
                {
                    "uri": f"gns3://projects/{project_id}/links/",
                    "name": f"Links in {proj['name']}",
                    "description": f"List of links in project {proj['name']}",
                    "mimeType": "application/json"
                },
                {
                    "uri": f"gns3://projects/{project_id}/templates/",
                    "name": f"Templates in {proj['name']}",
                    "description": f"Available templates for project {proj['name']}",
                    "mimeType": "application/json"
                },
                {
                    "uri": f"gns3://projects/{project_id}/drawings/",
                    "name": f"Drawings in {proj['name']}",
                    "description": f"List of drawings in project {proj['name']}",
                    "mimeType": "application/json"
                },
                {
                    "uri": f"gns3://projects/{project_id}/snapshots/",
                    "name": f"Snapshots in {proj['name']}",
                    "description": f"List of snapshots in project {proj['name']}",
                    "mimeType": "application/json"
                },
            ])

        # Session resources
        resources.extend([
            {
                "uri": "gns3://sessions/console/",
                "name": "Console Sessions",
                "description": "List of active console sessions",
                "mimeType": "application/json"
            },
            {
                "uri": "gns3://sessions/ssh/",
                "name": "SSH Sessions",
                "description": "List of active SSH sessions",
                "mimeType": "application/json"
            },
            {
                "uri": "gns3://proxy/status",
                "name": "SSH Proxy Status",
                "description": "SSH proxy service status",
                "mimeType": "application/json"
            },
            {
                "uri": "gns3://proxy/sessions",
                "name": "SSH Proxy Sessions",
                "description": "All SSH proxy sessions",
                "mimeType": "application/json"
            },
        ])

        return resources

    # ========================================================================
    # Project Resource Handlers
    # ========================================================================

    async def list_projects(self) -> str:
        """List all GNS3 projects"""
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

    async def list_templates(self, project_id: str) -> str:
        """List available templates"""
        from .project_resources import list_templates_impl
        return await list_templates_impl(self.app, project_id)

    async def list_drawings(self, project_id: str) -> str:
        """List drawings in project"""
        from .project_resources import list_drawings_impl
        return await list_drawings_impl(self.app, project_id)

    async def list_snapshots(self, project_id: str) -> str:
        """List snapshots in project"""
        from .project_resources import list_snapshots_impl
        return await list_snapshots_impl(self.app, project_id)

    async def get_snapshot(self, project_id: str, snapshot_id: str) -> str:
        """Get snapshot details"""
        from .project_resources import get_snapshot_impl
        return await get_snapshot_impl(self.app, project_id, snapshot_id)

    # ========================================================================
    # Session Resource Handlers
    # ========================================================================

    async def list_console_sessions(self) -> str:
        """List all active console sessions"""
        from .session_resources import list_console_sessions_impl
        return await list_console_sessions_impl(self.app)

    async def get_console_session(self, node_name: str) -> str:
        """Get console session status"""
        from .session_resources import get_console_session_impl
        return await get_console_session_impl(self.app, node_name)

    async def list_ssh_sessions(self) -> str:
        """List all active SSH sessions"""
        from .session_resources import list_ssh_sessions_impl
        return await list_ssh_sessions_impl(self.app)

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

    async def list_proxy_sessions(self) -> str:
        """List all SSH proxy sessions"""
        from .session_resources import list_proxy_sessions_impl
        return await list_proxy_sessions_impl(self.app)
