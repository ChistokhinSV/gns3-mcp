"""Structured exception hierarchy for GNS3 MCP server.

Provides consistent error handling with error codes and rich context.
All exceptions inherit from GNS3Error base class.

Example Usage:
    try:
        await gns3.start_node(project_id, node_id)
    except NodeNotFoundError as e:
        return format_error(
            error=str(e),
            error_code=e.error_code,
            suggestions=e.suggestions
        )
    except GNS3APIError as e:
        logger.error(f"API error {e.status_code}: {e.message}")
        return format_error(...)
"""

from typing import Any, Dict, List, Optional


class GNS3Error(Exception):
    """Base exception for all GNS3 operations.

    All GNS3-specific exceptions inherit from this class, allowing
    catch-all error handling when needed.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code (e.g., "NODE_NOT_FOUND")
        details: Optional dictionary with additional error context
        suggestions: List of actionable suggestions for the user
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestions = suggestions or []
        super().__init__(message)

    def __str__(self) -> str:
        """Return formatted error message with code."""
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "suggestions": self.suggestions,
        }


class GNS3NetworkError(GNS3Error):
    """Network connectivity error - cannot reach GNS3 server.

    Raised when:
    - GNS3 server is unreachable
    - Connection timeout
    - DNS resolution failed
    - Network interface down

    Example:
        raise GNS3NetworkError(
            f"Cannot connect to GNS3 server at {host}:{port}",
            details={"host": host, "port": port, "timeout": timeout},
            suggestions=[
                "Check GNS3 server is running",
                "Verify network connectivity",
                "Check firewall settings"
            ]
        )
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
    ):
        default_suggestions = [
            "Verify GNS3 server is running",
            "Check network connectivity to server",
            "Check firewall/antivirus blocking connection",
        ]
        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            details=details,
            suggestions=suggestions or default_suggestions,
        )


class GNS3APIError(GNS3Error):
    """GNS3 API returned HTTP error status.

    Raised when GNS3 server returns 4xx or 5xx HTTP status.
    Includes HTTP status code and response body for debugging.

    Attributes:
        status_code: HTTP status code (e.g., 404, 500)
        response_text: Raw response body from server

    Example:
        raise GNS3APIError(
            status_code=404,
            message="Project not found",
            response_text='{"message": "Project ID abc123 does not exist"}',
            suggestions=["Check project ID is correct", "List projects to find valid IDs"]
        )
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        response_text: str = "",
        suggestions: Optional[List[str]] = None,
    ):
        self.status_code = status_code
        self.response_text = response_text

        super().__init__(
            message=f"HTTP {status_code}: {message}",
            error_code=f"API_ERROR_{status_code}",
            details={"status_code": status_code, "response": response_text},
            suggestions=suggestions or [f"Check API documentation for HTTP {status_code} errors"],
        )


class GNS3AuthError(GNS3Error):
    """Authentication or authorization failed.

    Raised when:
    - Invalid username/password
    - JWT token expired
    - Insufficient permissions
    - Authentication required but not provided

    Example:
        raise GNS3AuthError(
            "Invalid username or password",
            suggestions=[
                "Check GNS3 username and password in .env file",
                "Verify GNS3 server authentication is enabled",
                "Test credentials with: curl -u user:pass http://server/v3/version"
            ]
        )
    """

    def __init__(self, message: str, suggestions: Optional[List[str]] = None):
        default_suggestions = [
            "Check username and password configuration",
            "Verify GNS3 server authentication settings",
            "Check server logs for authentication errors",
        ]
        super().__init__(
            message=message,
            error_code="AUTH_FAILED",
            details={},
            suggestions=suggestions or default_suggestions,
        )


class NodeNotFoundError(GNS3Error):
    """Node not found in project.

    Raised when attempting to access node that doesn't exist.

    Attributes:
        node_name: Name of the node that wasn't found
        project_id: Project ID where node was searched

    Example:
        raise NodeNotFoundError(
            node_name="Router1",
            project_id="abc123",
            available_nodes=["Router2", "Switch1"]
        )
    """

    def __init__(
        self,
        node_name: str,
        project_id: str,
        available_nodes: Optional[List[str]] = None,
    ):
        self.node_name = node_name
        self.project_id = project_id

        suggestions = [f"Check node name spelling: '{node_name}'"]
        if available_nodes:
            suggestions.append(f"Available nodes: {', '.join(available_nodes[:5])}")
            if len(available_nodes) > 5:
                suggestions.append(f"... and {len(available_nodes) - 5} more")

        super().__init__(
            message=f"Node '{node_name}' not found in project",
            error_code="NODE_NOT_FOUND",
            details={"node_name": node_name, "project_id": project_id},
            suggestions=suggestions,
        )


class ProjectNotFoundError(GNS3Error):
    """Project not found.

    Raised when attempting to access project that doesn't exist.

    Attributes:
        project_name: Name of the project that wasn't found
        available_projects: List of available project names

    Example:
        raise ProjectNotFoundError(
            project_name="MyLab",
            available_projects=["Lab1", "Lab2", "Production"]
        )
    """

    def __init__(
        self, project_name: str, available_projects: Optional[List[str]] = None
    ):
        self.project_name = project_name

        suggestions = [f"Check project name spelling: '{project_name}'"]
        if available_projects:
            suggestions.append("Available projects:")
            suggestions.extend([f"  - {name}" for name in available_projects[:5]])
            if len(available_projects) > 5:
                suggestions.append(f"  ... and {len(available_projects) - 5} more")

        super().__init__(
            message=f"Project '{project_name}' not found",
            error_code="PROJECT_NOT_FOUND",
            details={"project_name": project_name},
            suggestions=suggestions,
        )


class NodeStateError(GNS3Error):
    """Node is in invalid state for requested operation.

    Raised when operation requires specific node state.
    Example: Cannot rename running node, must stop first.

    Attributes:
        node_name: Name of the node
        current_state: Current node state (started, stopped, suspended)
        required_state: Required state for operation

    Example:
        raise NodeStateError(
            node_name="Router1",
            current_state="started",
            required_state="stopped",
            operation="rename"
        )
    """

    def __init__(
        self,
        node_name: str,
        current_state: str,
        required_state: str,
        operation: str,
    ):
        self.node_name = node_name
        self.current_state = current_state
        self.required_state = required_state

        super().__init__(
            message=f"Cannot {operation} node '{node_name}': currently {current_state}, requires {required_state}",
            error_code="INVALID_NODE_STATE",
            details={
                "node_name": node_name,
                "current_state": current_state,
                "required_state": required_state,
                "operation": operation,
            },
            suggestions=[
                f"Stop node first: set_node_properties('{node_name}', action='stop')",
                f"Wait for node to reach {required_state} state",
                "Check node status with resource nodes://<project_id>/",
            ],
        )


class ConsoleError(GNS3Error):
    """Console operation failed.

    Raised when console connection or operation fails.

    Example:
        raise ConsoleError(
            node_name="Router1",
            message="Connection refused on console port 5000",
            suggestions=[
                "Verify node is started",
                "Wait 30-60 seconds after node start",
                "Check console type is 'telnet' (not vnc/spice)"
            ]
        )
    """

    def __init__(self, node_name: str, message: str, suggestions: Optional[List[str]] = None):
        default_suggestions = [
            f"Verify node '{node_name}' is started",
            "Wait 30-60 seconds after starting node",
            "Check console type is 'telnet' (not vnc/spice/none)",
        ]
        super().__init__(
            message=f"Console error for '{node_name}': {message}",
            error_code="CONSOLE_ERROR",
            details={"node_name": node_name},
            suggestions=suggestions or default_suggestions,
        )


class SSHError(GNS3Error):
    """SSH operation failed.

    Raised when SSH connection or command execution fails.

    Example:
        raise SSHError(
            node_name="Router1",
            message="Authentication failed",
            suggestions=[
                "Check SSH credentials in device_dict",
                "Verify SSH is enabled on device",
                "Test SSH manually: ssh admin@10.10.10.1"
            ]
        )
    """

    def __init__(self, node_name: str, message: str, suggestions: Optional[List[str]] = None):
        default_suggestions = [
            f"Verify SSH is configured on '{node_name}'",
            "Check credentials in device_dict parameter",
            "Verify device is reachable from SSH proxy",
        ]
        super().__init__(
            message=f"SSH error for '{node_name}': {message}",
            error_code="SSH_ERROR",
            details={"node_name": node_name},
            suggestions=suggestions or default_suggestions,
        )


class ValidationError(GNS3Error):
    """Input validation failed.

    Raised when tool parameters are invalid.

    Example:
        raise ValidationError(
            message="Invalid action parameter",
            field="action",
            value="startt",  # Typo
            valid_values=["start", "stop", "suspend", "reload", "restart"]
        )
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        valid_values: Optional[List[str]] = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["provided_value"] = value
        if valid_values:
            details["valid_values"] = valid_values

        suggestions = []
        if valid_values:
            suggestions.append(f"Valid values for '{field}': {', '.join(valid_values)}")
        if value and valid_values:
            suggestions.append(f"Did you mean one of: {', '.join(valid_values)}")

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            suggestions=suggestions,
        )
