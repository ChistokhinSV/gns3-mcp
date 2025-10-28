"""GNS3 API v3 Client

Handles authentication and API interactions with GNS3 server.
Based on actual traffic analysis from GNS3 v3.0.5.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

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

    async def authenticate(self, retry: bool = False, retry_interval: int = 30,
                          max_retries: Optional[int] = None) -> bool:
        """Authenticate and obtain JWT token

        POST /v3/access/users/authenticate
        Body: {"username": "admin", "password": "password"}
        Response: {"access_token": "JWT", "token_type": "bearer"}

        Args:
            retry: If True, retry on failure (default: False)
            retry_interval: Seconds to wait between retries (default: 30)
            max_retries: Maximum number of retry attempts, None = infinite (default: None)

        Returns:
            True if authentication succeeded, False if failed without retry
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self.client.post(
                    f"{self.base_url}/v3/access/users/authenticate",
                    json={"username": self.username, "password": self.password}
                )
                response.raise_for_status()
                data = response.json()
                self.token = data["access_token"]
                if attempt > 1:
                    logger.info(f"[{datetime.now().strftime('%H:%M:%S %d.%m.%Y')}] Authentication succeeded on attempt {attempt}")
                else:
                    logger.info(f"[{datetime.now().strftime('%H:%M:%S %d.%m.%Y')}] Authenticated to GNS3 server at {self.base_url}")
                return True
            except Exception as e:
                if not retry or (max_retries is not None and attempt > max_retries):
                    logger.error(f"[{datetime.now().strftime('%H:%M:%S %d.%m.%Y')}] Authentication failed: {e}")
                    return False

                # Log retry attempt
                retry_msg = f"attempt {attempt}"
                if max_retries is not None:
                    retry_msg = f"attempt {attempt}/{max_retries}"

                logger.warning(f"[{datetime.now().strftime('%H:%M:%S %d.%m.%Y')}] Authentication failed ({retry_msg}): {e}")
                logger.info(f"[{datetime.now().strftime('%H:%M:%S %d.%m.%Y')}] Retrying in {retry_interval} seconds...")

                await asyncio.sleep(retry_interval)

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid token, authenticate if needed"""
        if not self.token:
            logger.info("No auth token - attempting authentication...")
            success = await self.authenticate(retry=True, retry_interval=5, max_retries=3)
            if not success:
                raise RuntimeError("Failed to authenticate with GNS3 server after multiple attempts")

    def _headers(self) -> Dict[str, str]:
        """Get headers with Bearer token"""
        if not self.token:
            raise RuntimeError("Not authenticated - call authenticate() first")
        return {"Authorization": f"Bearer {self.token}"}

    def _extract_error(self, exception: Exception) -> str:
        """Extract detailed error message from exception

        Args:
            exception: Exception from httpx

        Returns:
            Detailed error message
        """
        if isinstance(exception, httpx.HTTPStatusError):
            try:
                # Try to extract GNS3 API error message
                error_data = exception.response.json()
                if isinstance(error_data, dict):
                    # GNS3 API typically returns {"message": "error details"}
                    return error_data.get("message", str(exception))
                return str(exception)
            except (json.JSONDecodeError, AttributeError):
                # Fallback to generic message
                return f"HTTP {exception.response.status_code}: {exception.response.text[:200]}"
        return str(exception)

    async def get_projects(self) -> List[Dict[str, Any]]:
        """GET /v3/projects - list all projects"""
        await self._ensure_authenticated()
        response = await self.client.get(
            f"{self.base_url}/v3/projects",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def create_project(self, name: str, path: Optional[str] = None) -> Dict[str, Any]:
        """POST /v3/projects - create a new project

        Args:
            name: Project name
            path: Optional project directory path

        Returns:
            Created project data
        """
        payload = {"name": name}
        if path:
            payload["path"] = path

        response = await self.client.post(
            f"{self.base_url}/v3/projects",
            headers=self._headers(),
            json=payload
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

    async def close_project(self, project_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/close - close a project"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/close",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        return response.json()

    async def get_snapshots(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/snapshots - list all snapshots for a project

        Args:
            project_id: Project ID

        Returns:
            List of snapshot data dictionaries
        """
        response = await self.client.get(
            f"{self.base_url}/v3/projects/{project_id}/snapshots",
            headers=self._headers()
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
        # Handle empty response (204 No Content)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def stop_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/stop - stop a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/stop",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        # Handle empty response (204 No Content)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def suspend_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/suspend - suspend a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/suspend",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        # Handle empty response (204 No Content)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def reload_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/reload - reload a node"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/reload",
            headers=self._headers(),
            json={}
        )
        response.raise_for_status()
        # Handle empty response (204 No Content)
        if response.status_code == 204 or not response.content:
            return {}
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

    async def create_link(self, project_id: str, link_spec: Dict[str, Any],
                         timeout: float = 10.0) -> Dict[str, Any]:
        """POST /v3/projects/{id}/links - create a new link

        Args:
            project_id: Project ID
            link_spec: Link specification with nodes and ports
            timeout: Operation timeout in seconds
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/v3/projects/{project_id}/links",
                headers=self._headers(),
                json=link_spec,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to create link: {self._extract_error(e)}") from e

    async def delete_link(self, project_id: str, link_id: str,
                         timeout: float = 10.0) -> None:
        """DELETE /v3/projects/{id}/links/{link_id} - delete a link

        Args:
            project_id: Project ID
            link_id: Link ID to delete
            timeout: Operation timeout in seconds
        """
        try:
            response = await self.client.delete(
                f"{self.base_url}/v3/projects/{project_id}/links/{link_id}",
                headers=self._headers(),
                timeout=timeout
            )
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to delete link {link_id}: {self._extract_error(e)}") from e

    async def delete_node(self, project_id: str, node_id: str) -> None:
        """DELETE /v3/projects/{id}/nodes/{node_id} - delete a node"""
        response = await self.client.delete(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}",
            headers=self._headers()
        )
        response.raise_for_status()

    async def get_templates(self) -> List[Dict[str, Any]]:
        """GET /v3/templates - list all templates"""
        response = await self.client.get(
            f"{self.base_url}/v3/templates",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def get_template(self, template_id: str) -> Dict[str, Any]:
        """GET /v3/templates/{id} - get template details"""
        response = await self.client.get(
            f"{self.base_url}/v3/templates/{template_id}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def create_node_from_template(self, project_id: str, template_id: str,
                                       payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v3/projects/{id}/templates/{template_id} - create node from template"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/templates/{template_id}",
            headers=self._headers(),
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_drawings(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/drawings - list all drawings"""
        response = await self.client.get(
            f"{self.base_url}/v3/projects/{project_id}/drawings",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def create_drawing(self, project_id: str, drawing_data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v3/projects/{id}/drawings - create a drawing"""
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/drawings",
            headers=self._headers(),
            json=drawing_data
        )
        response.raise_for_status()
        return response.json()

    async def update_drawing(self, project_id: str, drawing_id: str,
                            drawing_data: Dict[str, Any]) -> Dict[str, Any]:
        """PUT /v3/projects/{id}/drawings/{drawing_id} - update a drawing"""
        response = await self.client.put(
            f"{self.base_url}/v3/projects/{project_id}/drawings/{drawing_id}",
            headers=self._headers(),
            json=drawing_data
        )
        response.raise_for_status()
        return response.json()

    async def delete_drawing(self, project_id: str, drawing_id: str) -> None:
        """DELETE /v3/projects/{id}/drawings/{drawing_id} - delete a drawing"""
        response = await self.client.delete(
            f"{self.base_url}/v3/projects/{project_id}/drawings/{drawing_id}",
            headers=self._headers()
        )
        response.raise_for_status()

    async def get_node_file(self, project_id: str, node_id: str, file_path: str) -> str:
        """GET /v3/projects/{id}/nodes/{node_id}/files/{path} - read file from node filesystem

        Args:
            project_id: Project ID
            node_id: Node ID
            file_path: Path relative to container root (e.g., 'etc/network/interfaces')

        Returns:
            File contents as string
        """
        response = await self.client.get(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/files/{file_path}",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.text

    async def write_node_file(self, project_id: str, node_id: str, file_path: str, content: str) -> None:
        """POST /v3/projects/{id}/nodes/{node_id}/files/{path} - write file to node filesystem

        Args:
            project_id: Project ID
            node_id: Node ID
            file_path: Path relative to container root (e.g., 'etc/network/interfaces')
            content: File contents to write
        """
        response = await self.client.post(
            f"{self.base_url}/v3/projects/{project_id}/nodes/{node_id}/files/{file_path}",
            headers={**self._headers(), "Content-Type": "text/plain"},
            content=content
        )
        response.raise_for_status()

    async def get_version(self) -> Dict[str, Any]:
        """GET /v3/version - get GNS3 server version"""
        response = await self.client.get(
            f"{self.base_url}/v3/version"
        )
        response.raise_for_status()
        return response.json()

    async def get_symbol_raw(self, symbol_id: str) -> bytes:
        """GET /v3/symbols/{symbol_id}/raw - get raw symbol file (PNG/SVG)

        Args:
            symbol_id: Symbol filename (e.g., 'mikrotik.png')

        Returns:
            Raw bytes of the symbol file
        """
        # URL-encode the symbol_id to handle paths like ':/symbols/...'
        import urllib.parse
        encoded_symbol = urllib.parse.quote(symbol_id, safe='')

        response = await self.client.get(
            f"{self.base_url}/v3/symbols/{encoded_symbol}/raw",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.content

    # Project Files API

    async def get_project_readme(self, project_id: str) -> str:
        """Get project README/notes

        GET /v3/projects/{project_id}/files/README.txt

        Args:
            project_id: Project ID

        Returns:
            README content as string, empty string if doesn't exist
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/v3/projects/{project_id}/files/README.txt",
                headers=self._headers()
            )
            if response.status_code == 404:
                return ""  # README doesn't exist yet
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ""
            logger.error(f"Failed to get README: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading README: {e}")
            raise

    async def update_project_readme(self, project_id: str, content: str) -> bool:
        """Update project README/notes

        POST /v3/projects/{project_id}/files/README.txt

        Args:
            project_id: Project ID
            content: README content to save

        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/v3/projects/{project_id}/files/README.txt",
                headers=self._headers(),
                content=content.encode('utf-8')
            )
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Failed to update README: {e}")
            return False

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
