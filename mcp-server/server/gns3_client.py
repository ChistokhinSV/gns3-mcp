"""GNS3 API v3 Client

Handles authentication and API interactions with GNS3 server.
Based on actual traffic analysis from GNS3 v3.0.5.
"""

import httpx
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class GNS3Client:
    """Async client for GNS3 v3 API"""

    def __init__(self, host: str = "localhost", port: int = 80,
                 username: str = "admin", password: str = ""):
        self.base_url = f"http://{host}:{port}"
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=30.0)

    async def authenticate(self) -> bool:
        """Authenticate and obtain JWT token

        POST /v3/access/users/authenticate
        Body: {"username": "admin", "password": "password"}
        Response: {"access_token": "JWT", "token_type": "bearer"}
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/v3/access/users/authenticate",
                json={"username": self.username, "password": self.password}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data["access_token"]
            logger.info(f"Authenticated to GNS3 server at {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def _headers(self) -> Dict[str, str]:
        """Get headers with Bearer token"""
        if not self.token:
            raise RuntimeError("Not authenticated - call authenticate() first")
        return {"Authorization": f"Bearer {self.token}"}

    async def get_projects(self) -> List[Dict[str, Any]]:
        """GET /v3/projects - list all projects"""
        response = await self.client.get(
            f"{self.base_url}/v3/projects",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def open_project(self, project_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/open - open a project"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/open",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        return response.json()

    async def get_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/nodes - list all nodes in project"""
        response = await self.client.get(
            f"{self.base_url}/v3/projects/{project_id}/nodes",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def get_links(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/links - list all links in project"""
        response = await self.client.get(
            f"{self.base_url}/v3/projects/{project_id}/links",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def start_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/start - start a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/start",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        return response.json()

    async def stop_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/stop - stop a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/stop",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        return response.json()

    async def suspend_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/suspend - suspend a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/suspend",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        return response.json()

    async def reload_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/reload - reload a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/reload",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        return response.json()

    async def update_node(self, project_id: str, node_id: str,
                         properties: Dict[str, Any]) -> Dict[str, Any]:
        """PUT /v3/projects/{id}/nodes/{node_id} - update node properties

        Args:
            project_id: Project ID
            node_id: Node ID
            properties: Dict with properties to update (x, y, z, locked, ports, etc.)
        """
        response = await self.client.put(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}",
            headers=self._headers(),
            json=properties
        )
        response.raise_for_status()
        return response.json()

    async def create_link(self, project_id: str, link_spec: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v3/projects/{id}/links - create a new link

        Args:
            project_id: Project ID
            link_spec: Link specification with nodes and ports
        """
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/links",
            headers=self._headers(),
            json=link_spec
        )
        response.raise_for_status()
        return response.json()

    async def delete_link(self, project_id: str, link_id: str) -> None:
        """DELETE /v3/projects/{id}/links/{link_id} - delete a link"""
        response = await self.client.delete(
            f"{self.base_url}/v3/projects/{project_id}/links/{link_id}",
            headers=self._headers()
        )
        response.raise_for_status()

    async def get_version(self) -> Dict[str, Any]:
        """GET /v3/version - get GNS3 server version"""
        response = await self.client.get(
            f"{self.base_url}/v3/version"
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
