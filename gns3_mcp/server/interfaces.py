"""Abstract Base Classes for GNS3 MCP Server

Defines interfaces for all major components to enable dependency inversion,
facilitate testing with mocks, and clarify component contracts.

v0.49.0: Initial interface definitions for architecture refactoring
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IGns3Client(ABC):
    """Abstract interface for GNS3 v3 API client

    Defines the contract for interacting with GNS3 server API.
    """

    # Connection management
    @abstractmethod
    async def authenticate(
        self, retry: bool = False, retry_interval: int = 30, max_retries: int | None = None
    ) -> bool:
        """Authenticate and obtain JWT token

        Args:
            retry: If True, retry on failure
            retry_interval: Seconds to wait between retries
            max_retries: Maximum number of retry attempts, None = infinite

        Returns:
            True if authentication succeeded, False if failed without retry
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close HTTP client"""
        pass

    # Project operations
    @abstractmethod
    async def get_projects(self) -> List[Dict[str, Any]]:
        """GET /v3/projects - list all projects"""
        pass

    @abstractmethod
    async def create_project(self, name: str, path: str | None = None) -> Dict[str, Any]:
        """POST /v3/projects - create a new project

        Args:
            name: Project name
            path: Optional project directory path

        Returns:
            Created project data
        """
        pass

    @abstractmethod
    async def open_project(self, project_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/open - open a project"""
        pass

    @abstractmethod
    async def close_project(self, project_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/close - close a project"""
        pass

    @abstractmethod
    async def get_snapshots(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/snapshots - list all snapshots for a project"""
        pass

    # Node operations
    @abstractmethod
    async def get_nodes(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/nodes - list all nodes in project"""
        pass

    @abstractmethod
    async def start_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/start - start a node"""
        pass

    @abstractmethod
    async def stop_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/stop - stop a node"""
        pass

    @abstractmethod
    async def suspend_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/suspend - suspend a node"""
        pass

    @abstractmethod
    async def reload_node(self, project_id: str, node_id: str) -> Dict[str, Any]:
        """POST /v3/projects/{id}/nodes/{node_id}/reload - reload a node"""
        pass

    @abstractmethod
    async def update_node(
        self, project_id: str, node_id: str, properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """PUT /v3/projects/{id}/nodes/{node_id} - update node properties

        Args:
            project_id: Project ID
            node_id: Node ID
            properties: Dict with properties to update (x, y, z, locked, ports, etc.)
        """
        pass

    @abstractmethod
    async def delete_node(self, project_id: str, node_id: str) -> None:
        """DELETE /v3/projects/{id}/nodes/{node_id} - delete a node"""
        pass

    # Link operations
    @abstractmethod
    async def get_links(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/links - list all links in project"""
        pass

    @abstractmethod
    async def create_link(
        self, project_id: str, link_spec: Dict[str, Any], timeout: float = 10.0
    ) -> Dict[str, Any]:
        """POST /v3/projects/{id}/links - create a new link

        Args:
            project_id: Project ID
            link_spec: Link specification with nodes and ports
            timeout: Operation timeout in seconds
        """
        pass

    @abstractmethod
    async def delete_link(self, project_id: str, link_id: str, timeout: float = 10.0) -> None:
        """DELETE /v3/projects/{id}/links/{link_id} - delete a link

        Args:
            project_id: Project ID
            link_id: Link ID to delete
            timeout: Operation timeout in seconds
        """
        pass

    # Template operations
    @abstractmethod
    async def get_templates(self) -> List[Dict[str, Any]]:
        """GET /v3/templates - list all templates"""
        pass

    @abstractmethod
    async def get_template(self, template_id: str) -> Dict[str, Any]:
        """GET /v3/templates/{id} - get template details"""
        pass

    @abstractmethod
    async def create_node_from_template(
        self, project_id: str, template_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """POST /v3/projects/{id}/templates/{template_id} - create node from template"""
        pass

    # Drawing operations
    @abstractmethod
    async def get_drawings(self, project_id: str) -> List[Dict[str, Any]]:
        """GET /v3/projects/{id}/drawings - list all drawings"""
        pass

    @abstractmethod
    async def create_drawing(self, project_id: str, drawing_data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v3/projects/{id}/drawings - create a drawing"""
        pass

    @abstractmethod
    async def update_drawing(
        self, project_id: str, drawing_id: str, drawing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """PUT /v3/projects/{id}/drawings/{drawing_id} - update a drawing"""
        pass

    @abstractmethod
    async def delete_drawing(self, project_id: str, drawing_id: str) -> None:
        """DELETE /v3/projects/{id}/drawings/{drawing_id} - delete a drawing"""
        pass

    # File operations
    @abstractmethod
    async def get_node_file(self, project_id: str, node_id: str, file_path: str) -> str:
        """GET /v3/projects/{id}/nodes/{node_id}/files/{path} - read file from node filesystem

        Args:
            project_id: Project ID
            node_id: Node ID
            file_path: Path relative to container root

        Returns:
            File contents as string
        """
        pass

    @abstractmethod
    async def write_node_file(
        self, project_id: str, node_id: str, file_path: str, content: str
    ) -> None:
        """POST /v3/projects/{id}/nodes/{node_id}/files/{path} - write file to node filesystem

        Args:
            project_id: Project ID
            node_id: Node ID
            file_path: Path relative to container root
            content: File contents to write
        """
        pass

    @abstractmethod
    async def get_project_readme(self, project_id: str) -> str:
        """GET /v3/projects/{project_id}/files/README.txt - get project README/notes

        Args:
            project_id: Project ID

        Returns:
            README content as string, empty string if doesn't exist
        """
        pass

    @abstractmethod
    async def update_project_readme(self, project_id: str, content: str) -> bool:
        """POST /v3/projects/{project_id}/files/README.txt - update project README/notes

        Args:
            project_id: Project ID
            content: README content to save

        Returns:
            True if successful, False otherwise
        """
        pass

    # Symbol operations
    @abstractmethod
    async def get_symbol_raw(self, symbol_id: str) -> bytes:
        """GET /v3/symbols/{symbol_id}/raw - get raw symbol file (PNG/SVG)

        Args:
            symbol_id: Symbol filename

        Returns:
            Raw bytes of the symbol file
        """
        pass

    @abstractmethod
    async def get_version(self) -> Dict[str, Any]:
        """GET /v3/version - get GNS3 server version"""
        pass

    # Connection state attributes (not properties - simple state variables)
    # These are set in __init__ and updated during operation:
    # - base_url: str
    # - is_connected: bool
    # - connection_error: str | None


class IConsoleManager(ABC):
    """Abstract interface for console session management

    Defines the contract for managing telnet connections to GNS3 node consoles.
    """

    @abstractmethod
    async def connect(self, host: str, port: int, node_name: str) -> str:
        """Connect to a console and return session ID

        Args:
            host: Console host (GNS3 server IP)
            port: Console port number
            node_name: Name of the node for logging

        Returns:
            session_id: Unique session identifier
        """
        pass

    @abstractmethod
    async def send(self, session_id: str, data: str) -> bool:
        """Send data to console

        Args:
            session_id: Session identifier
            data: Data to send (command or keystrokes)

        Returns:
            Success status
        """
        pass

    @abstractmethod
    def get_output(self, session_id: str) -> str | None:
        """Get current console output buffer

        Args:
            session_id: Session identifier

        Returns:
            Full console buffer (ANSI codes stripped) or None if session not found
        """
        pass

    @abstractmethod
    def get_diff(self, session_id: str) -> str | None:
        """Get new console output since last read

        Args:
            session_id: Session identifier

        Returns:
            New output since last read (ANSI codes stripped), or None if session not found
        """
        pass

    @abstractmethod
    def has_accessed_terminal(self, session_id: str) -> bool:
        """Check if terminal has been accessed (read) at least once

        Args:
            session_id: Session identifier

        Returns:
            True if terminal has been read, False otherwise or if session not found
        """
        pass

    @abstractmethod
    def has_accessed_terminal_by_node(self, node_name: str) -> bool:
        """Check if terminal has been accessed (read) at least once by node name

        Args:
            node_name: Name of the node

        Returns:
            True if terminal has been read, False otherwise or if session not found
        """
        pass

    @abstractmethod
    async def disconnect(self, session_id: str) -> bool:
        """Disconnect console session

        Args:
            session_id: Session identifier

        Returns:
            Success status
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> None:
        """Remove expired sessions"""
        pass

    @abstractmethod
    async def close_all(self) -> None:
        """Close all console sessions"""
        pass

    @abstractmethod
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active sessions

        Returns:
            Dict of session info keyed by session_id
        """
        pass

    # Node-name based convenience methods
    @abstractmethod
    def get_session_id(self, node_name: str) -> str | None:
        """Get session ID for a node

        Args:
            node_name: Node name

        Returns:
            session_id or None if not found
        """
        pass

    @abstractmethod
    def has_session(self, node_name: str) -> bool:
        """Check if a session exists for a node

        Args:
            node_name: Node name

        Returns:
            True if session exists and is active
        """
        pass

    @abstractmethod
    async def send_by_node(self, node_name: str, data: str) -> bool:
        """Send data to console by node name

        Args:
            node_name: Node name
            data: Data to send

        Returns:
            Success status
        """
        pass

    @abstractmethod
    def get_output_by_node(self, node_name: str) -> str | None:
        """Get console output by node name

        Args:
            node_name: Node name

        Returns:
            Console buffer or None
        """
        pass

    @abstractmethod
    def get_diff_by_node(self, node_name: str) -> str | None:
        """Get new console output by node name

        Args:
            node_name: Node name

        Returns:
            New output since last read or None
        """
        pass

    @abstractmethod
    async def disconnect_by_node(self, node_name: str) -> bool:
        """Disconnect console by node name

        Args:
            node_name: Node name

        Returns:
            Success status
        """
        pass


class IResourceManager(ABC):
    """Abstract interface for MCP resource management

    Defines the contract for managing and serving MCP protocol resources.
    """

    @abstractmethod
    def parse_uri(self, uri: str) -> tuple[str | None, Dict[str, str] | None]:
        """Parse resource URI and extract handler name and parameters

        Args:
            uri: Resource URI (e.g., projects://abc123/nodes/)

        Returns:
            Tuple of (handler_name, parameters_dict) or (None, None) if no match
        """
        pass

    @abstractmethod
    async def get_resource(self, uri: str) -> str:
        """Get resource by URI

        Args:
            uri: Resource URI

        Returns:
            JSON string with resource data or error
        """
        pass

    @abstractmethod
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List all available resources

        Returns:
            List of resource metadata dicts
        """
        pass

    # Project resources
    @abstractmethod
    async def list_projects(self) -> str:
        """List all GNS3 projects with their statuses and IDs"""
        pass

    @abstractmethod
    async def get_project(self, project_id: str) -> str:
        """Get project details"""
        pass

    @abstractmethod
    async def list_nodes(self, project_id: str) -> str:
        """List nodes in project"""
        pass

    @abstractmethod
    async def get_node(self, project_id: str, node_id: str) -> str:
        """Get node details"""
        pass

    @abstractmethod
    async def list_links(self, project_id: str) -> str:
        """List links in project"""
        pass

    @abstractmethod
    async def list_templates(self) -> str:
        """List available templates"""
        pass

    @abstractmethod
    async def list_drawings(self, project_id: str) -> str:
        """List drawings in project"""
        pass

    @abstractmethod
    async def get_project_readme(self, project_id: str) -> str:
        """Get project README/notes"""
        pass

    @abstractmethod
    async def get_topology_report(self, project_id: str) -> str:
        """Get unified topology report with nodes, links, and statistics"""
        pass

    @abstractmethod
    async def get_template(self, template_id: str) -> str:
        """Get template details with usage notes"""
        pass

    @abstractmethod
    async def get_node_template_usage(self, project_id: str, node_id: str) -> str:
        """Get template usage notes for a specific node"""
        pass

    # Session resources
    @abstractmethod
    async def list_console_sessions(self, project_id: str | None = None) -> str:
        """List all active console sessions (optionally filtered by project_id)"""
        pass

    @abstractmethod
    async def get_console_session(self, node_name: str) -> str:
        """Get console session status"""
        pass

    @abstractmethod
    async def list_ssh_sessions(self, project_id: str | None = None) -> str:
        """List all active SSH sessions (optionally filtered by project_id)"""
        pass

    @abstractmethod
    async def get_ssh_session(self, node_name: str) -> str:
        """Get SSH session status"""
        pass

    @abstractmethod
    async def get_ssh_history(self, node_name: str) -> str:
        """Get SSH command history"""
        pass

    @abstractmethod
    async def get_ssh_buffer(self, node_name: str) -> str:
        """Get SSH continuous buffer"""
        pass

    # Proxy resources
    @abstractmethod
    async def get_proxy_status(self) -> str:
        """Get SSH proxy service status"""
        pass

    @abstractmethod
    async def get_proxy_registry(self) -> str:
        """Get proxy registry (discovered lab proxies)"""
        pass

    @abstractmethod
    async def list_proxy_sessions(self) -> str:
        """List all SSH proxy sessions"""
        pass

    @abstractmethod
    async def list_project_proxies(self, project_id: str) -> str:
        """List proxies for specific project"""
        pass

    @abstractmethod
    async def get_proxy(self, proxy_id: str) -> str:
        """Get specific proxy details by proxy_id"""
        pass


class IAppContext(ABC):
    """Abstract interface for application context

    Defines the contract for the main application context that holds
    all major components and shared state.

    Note: This interface uses simple attributes (not properties) for most fields
    to match the dataclass implementation pattern. Only resource_manager and
    current_project_id use property setters for lifecycle management.
    """

    # Simple attributes (set in __init__, accessed during operation)
    # These are not @property/@abstractmethod because they're dataclass fields:
    # - gns3: IGns3Client - GNS3 API client
    # - console: IConsoleManager - Console session manager
    # - dependencies: Dependencies - DI container
    # - ssh_proxy_mapping: Dict[str, str] - Node name to proxy URL mapping

    @property
    @abstractmethod
    def resource_manager(self) -> IResourceManager | None:
        """Get resource manager (may be None during initialization)"""
        pass

    @resource_manager.setter
    @abstractmethod
    def resource_manager(self, value: IResourceManager) -> None:
        """Set resource manager"""
        pass

    @property
    @abstractmethod
    def current_project_id(self) -> str | None:
        """Get current project ID (None if no project open)"""
        pass

    @current_project_id.setter
    @abstractmethod
    def current_project_id(self, value: str | None) -> None:
        """Set current project ID"""
        pass
