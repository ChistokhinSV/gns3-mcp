"""
Docker API Proxy Discovery

Discovers lab proxies via Docker API by:
1. Finding containers with gns3-ssh-proxy image and /gns3/init.sh entrypoint
2. Extracting project_id and node_id from mount paths
3. Querying GNS3 API for external console ports
4. Building proxy registry with URLs

Only used by the main proxy on GNS3 host (with /var/run/docker.sock mounted).
Lab proxies don't need Docker API access.
"""

import logging
import re
from typing import Optional, List, Dict, Any
import docker
from docker.errors import DockerException
import httpx

logger = logging.getLogger(__name__)


class ProxyInfo:
    """Information about a discovered lab proxy"""

    def __init__(
        self,
        proxy_id: str,
        hostname: str,
        project_id: str,
        container_id: str,
        image: str,
        url: Optional[str] = None,
        console_port: Optional[int] = None
    ):
        self.proxy_id = proxy_id  # GNS3 node_id (persistent)
        self.hostname = hostname  # Exact GNS3 node name
        self.project_id = project_id
        self.container_id = container_id  # For reference only
        self.image = image
        self.url = url  # http://gns3_host:console_port
        self.console_port = console_port

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'proxy_id': self.proxy_id,
            'hostname': self.hostname,
            'project_id': self.project_id,
            'container_id': self.container_id,
            'image': self.image,
            'url': self.url,
            'console_port': self.console_port,
            'discovered_via': 'docker_api'
        }


class DockerProxyDiscovery:
    """Discovers lab proxies via Docker API"""

    def __init__(self, gns3_host: str, gns3_port: int = 80,
                 gns3_username: str = "admin", gns3_password: str = ""):
        """
        Initialize discovery service

        Args:
            gns3_host: GNS3 server hostname/IP
            gns3_port: GNS3 API port (default: 80)
            gns3_username: GNS3 username for API auth
            gns3_password: GNS3 password for API auth
        """
        self.gns3_host = gns3_host
        self.gns3_port = gns3_port
        self.gns3_username = gns3_username
        self.gns3_password = gns3_password
        self.gns3_token: Optional[str] = None

        # Docker client (will use /var/run/docker.sock if available)
        self.docker_client: Optional[docker.DockerClient] = None
        self.docker_available = False

        self._initialize_docker()

    def _initialize_docker(self):
        """Initialize Docker client"""
        try:
            self.docker_client = docker.from_env()
            # Test connection
            self.docker_client.ping()
            self.docker_available = True
            logger.info("Docker API available - proxy discovery enabled")
        except DockerException as e:
            logger.warning(f"Docker API not available: {e}. Proxy discovery disabled.")
            logger.info("To enable discovery, mount /var/run/docker.sock to the container")
            self.docker_available = False

    async def _authenticate_gns3(self) -> bool:
        """
        Authenticate to GNS3 API and get JWT token

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"http://{self.gns3_host}:{self.gns3_port}/v3/access/users/authenticate",
                    json={"username": self.gns3_username, "password": self.gns3_password}
                )
                response.raise_for_status()
                data = response.json()
                self.gns3_token = data["access_token"]
                logger.info("Authenticated to GNS3 API for proxy discovery")
                return True
        except Exception as e:
            logger.error(f"GNS3 authentication failed: {e}")
            return False

    async def _get_node_console_port(self, project_id: str, node_id: str) -> Optional[int]:
        """
        Query GNS3 API for node's external console port

        Args:
            project_id: GNS3 project UUID
            node_id: GNS3 node UUID

        Returns:
            External console port number, or None if not found
        """
        if not self.gns3_token:
            if not await self._authenticate_gns3():
                return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/nodes/{node_id}",
                    headers={"Authorization": f"Bearer {self.gns3_token}"}
                )
                response.raise_for_status()
                node = response.json()
                return node.get('console')
        except Exception as e:
            logger.error(f"Failed to get console port for node {node_id}: {e}")
            return None

    async def discover_proxies(self) -> List[ProxyInfo]:
        """
        Discover all lab proxies via Docker API

        Returns:
            List of ProxyInfo objects for discovered lab proxies
        """
        if not self.docker_available or not self.docker_client:
            logger.warning("Docker API not available - cannot discover proxies")
            return []

        proxies = []

        try:
            # Find all gns3-ssh-proxy containers
            containers = self.docker_client.containers.list(
                filters={"ancestor": "chistokhinsv/gns3-ssh-proxy"}
            )

            logger.info(f"Found {len(containers)} gns3-ssh-proxy container(s)")

            for container in containers:
                # Check if it's a lab proxy (has /gns3/init.sh entrypoint)
                # Main proxy has path 'uvicorn' instead
                path = container.attrs.get('Path', '')
                if path != '/gns3/init.sh':
                    logger.debug(f"Skipping {container.short_id}: not a lab proxy (path={path})")
                    continue

                # Extract hostname (exact GNS3 node name)
                hostname = container.attrs['Config']['Hostname']

                # Extract project_id and node_id from mounts
                project_id = None
                node_id = None

                for mount in container.attrs.get('Mounts', []):
                    source = mount.get('Source', '')
                    # Match: /opt/gns3/projects/{project_id}/project-files/docker/{node_id}/
                    match = re.search(
                        r'/opt/gns3/projects/([0-9a-f-]+)/project-files/docker/([0-9a-f-]+)',
                        source
                    )
                    if match:
                        project_id = match.group(1)
                        node_id = match.group(2)
                        break

                if not project_id or not node_id:
                    logger.warning(f"Skipping {container.short_id}: couldn't extract project_id/node_id")
                    continue

                # Query GNS3 API for external console port
                console_port = await self._get_node_console_port(project_id, node_id)

                if not console_port:
                    logger.warning(f"Skipping {hostname}: couldn't get console port from GNS3 API")
                    continue

                # Build proxy URL
                url = f"http://{self.gns3_host}:{console_port}"

                proxy = ProxyInfo(
                    proxy_id=node_id,  # proxy_id = GNS3 node_id
                    hostname=hostname,
                    project_id=project_id,
                    container_id=container.short_id,
                    image=container.attrs['Config']['Image'],
                    url=url,
                    console_port=console_port
                )

                proxies.append(proxy)
                logger.info(f"Discovered lab proxy: {hostname} ({proxy.proxy_id}) at {url}")

        except DockerException as e:
            logger.error(f"Docker API error during discovery: {e}")

        return proxies

    def close(self):
        """Close Docker client"""
        if self.docker_client:
            self.docker_client.close()
