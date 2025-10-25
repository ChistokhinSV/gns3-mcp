"""Error utility functions for standardized error responses

Provides helper functions for creating consistent error responses across all tools.
All functions return JSON strings ready to be returned from MCP tools.
"""
from typing import Optional, Dict, Any, List
import json

# Import after main.py has loaded VERSION
def get_version():
    """Get VERSION from main module (deferred import to avoid circular dependency)"""
    try:
        from main import VERSION
        return VERSION
    except ImportError:
        return "unknown"


def create_error_response(
    error: str,
    error_code: str,
    details: Optional[str] = None,
    suggested_action: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Create standardized error response

    Args:
        error: Human-readable error message
        error_code: Machine-readable error code (from ErrorCode enum)
        details: Additional error details
        suggested_action: Suggested action to fix the error
        context: Error context for debugging

    Returns:
        JSON string with standardized error response
    """
    from models import ErrorResponse

    response = ErrorResponse(
        error=error,
        error_code=error_code,
        details=details,
        suggested_action=suggested_action,
        context=context,
        server_version=get_version()
    )
    return response.model_dump_json(indent=2)


# Common error response templates

def node_not_found_error(
    node_name: str,
    project_id: str,
    available_nodes: List[str]
) -> str:
    """Standard 'node not found' error

    Args:
        node_name: Name of node that was not found
        project_id: Project ID
        available_nodes: List of available node names

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Node '{node_name}' not found in project",
        error_code=ErrorCode.NODE_NOT_FOUND.value,
        details=f"Available nodes: {', '.join(available_nodes) if available_nodes else 'none'}",
        suggested_action="Use list_nodes() to see all available nodes in the project",
        context={
            "project_id": project_id,
            "node_name": node_name,
            "available_nodes": available_nodes
        }
    )


def project_not_found_error(project_name: Optional[str] = None) -> str:
    """Standard 'project not found' error

    Args:
        project_name: Name of project that was not found (None if no project open)

    Returns:
        JSON error response
    """
    from models import ErrorCode

    if project_name:
        error_msg = f"Project '{project_name}' not found"
        suggested_action = "Use list_projects() to see available projects, or check the project name spelling"
    else:
        error_msg = "No project currently open"
        suggested_action = "Use open_project() to open a project first"

    return create_error_response(
        error=error_msg,
        error_code=ErrorCode.PROJECT_NOT_FOUND.value,
        suggested_action=suggested_action,
        context={"project_name": project_name} if project_name else None
    )


def validation_error(
    message: str,
    parameter: str,
    value: Any,
    valid_values: Optional[List[Any]] = None
) -> str:
    """Standard validation error

    Args:
        message: Error message
        parameter: Parameter name that failed validation
        value: Invalid value that was provided
        valid_values: List of valid values (optional)

    Returns:
        JSON error response
    """
    from models import ErrorCode

    details = f"Invalid value '{value}' for parameter '{parameter}'"
    if valid_values:
        details += f". Valid values: {', '.join(map(str, valid_values))}"

    return create_error_response(
        error=message,
        error_code=ErrorCode.INVALID_PARAMETER.value,
        details=details,
        suggested_action=f"Check the '{parameter}' parameter and try again",
        context={
            "parameter": parameter,
            "value": value,
            "valid_values": valid_values
        }
    )


def gns3_api_error(
    status_code: int,
    message: str,
    endpoint: str
) -> str:
    """Standard GNS3 API error

    Args:
        status_code: HTTP status code
        message: Error message from API
        endpoint: API endpoint that failed

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"GNS3 API error: {message}",
        error_code=ErrorCode.GNS3_API_ERROR.value,
        details=f"HTTP {status_code} from {endpoint}",
        suggested_action="Check GNS3 server logs for details, or verify the request parameters",
        context={
            "status_code": status_code,
            "endpoint": endpoint,
            "message": message
        }
    )


def template_not_found_error(
    template_name: str,
    available_templates: List[str]
) -> str:
    """Standard 'template not found' error

    Args:
        template_name: Name of template that was not found
        available_templates: List of available template names

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Template '{template_name}' not found",
        error_code=ErrorCode.TEMPLATE_NOT_FOUND.value,
        details=f"Available templates: {', '.join(available_templates[:10]) if available_templates else 'none'}",
        suggested_action="Use list_templates() to see all available templates",
        context={
            "template_name": template_name,
            "available_templates": available_templates[:20]  # Limit context size
        }
    )


def drawing_not_found_error(
    drawing_id: str,
    project_id: str,
    available_ids: List[str]
) -> str:
    """Standard 'drawing not found' error

    Args:
        drawing_id: ID of drawing that was not found
        project_id: Project ID
        available_ids: List of available drawing IDs

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Drawing '{drawing_id}' not found in project",
        error_code=ErrorCode.DRAWING_NOT_FOUND.value,
        details=f"Available drawing IDs: {', '.join(available_ids) if available_ids else 'none'}",
        suggested_action="Use list_drawings() or resource gns3://projects/{id}/drawings/ to see available drawings",
        context={
            "project_id": project_id,
            "drawing_id": drawing_id,
            "available_ids": available_ids
        }
    )


def snapshot_not_found_error(
    snapshot_name: str,
    project_id: str,
    available_snapshots: List[str]
) -> str:
    """Standard 'snapshot not found' error

    Args:
        snapshot_name: Name of snapshot that was not found
        project_id: Project ID
        available_snapshots: List of available snapshot names

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Snapshot '{snapshot_name}' not found in project",
        error_code=ErrorCode.SNAPSHOT_NOT_FOUND.value,
        details=f"Available snapshots: {', '.join(available_snapshots) if available_snapshots else 'none'}",
        suggested_action="Use resource gns3://projects/{id}/snapshots/ to see available snapshots",
        context={
            "project_id": project_id,
            "snapshot_name": snapshot_name,
            "available_snapshots": available_snapshots
        }
    )


def port_in_use_error(
    node_name: str,
    adapter: int,
    port: int,
    connected_to: Optional[str] = None
) -> str:
    """Standard 'port in use' error

    Args:
        node_name: Node name
        adapter: Adapter number
        port: Port number
        connected_to: Name of node this port is connected to (optional)

    Returns:
        JSON error response
    """
    from models import ErrorCode

    error_msg = f"Port {node_name} adapter {adapter} port {port} is already connected"
    if connected_to:
        error_msg += f" to {connected_to}"

    return create_error_response(
        error=error_msg,
        error_code=ErrorCode.PORT_IN_USE.value,
        suggested_action="Disconnect the existing link first using set_connection with action='disconnect'",
        context={
            "node_name": node_name,
            "adapter": adapter,
            "port": port,
            "connected_to": connected_to
        }
    )


def node_running_error(
    node_name: str,
    operation: str
) -> str:
    """Standard 'node running' error

    Args:
        node_name: Node name
        operation: Operation that requires stopped node

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Operation '{operation}' requires node '{node_name}' to be stopped",
        error_code=ErrorCode.NODE_RUNNING.value,
        details="Node is currently running",
        suggested_action=f"Stop the node first with set_node('{node_name}', action='stop'), then retry",
        context={
            "node_name": node_name,
            "operation": operation
        }
    )


def node_stopped_error(
    node_name: str,
    operation: str
) -> str:
    """Standard 'node stopped' error

    Args:
        node_name: Node name
        operation: Operation that requires running node

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Operation '{operation}' requires node '{node_name}' to be running",
        error_code=ErrorCode.NODE_STOPPED.value,
        details="Node is currently stopped",
        suggested_action=f"Start the node first with set_node('{node_name}', action='start'), then retry",
        context={
            "node_name": node_name,
            "operation": operation
        }
    )


def gns3_unreachable_error(host: str, port: int, details: str) -> str:
    """Standard 'GNS3 unreachable' error

    Args:
        host: GNS3 host
        port: GNS3 port
        details: Error details

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Cannot connect to GNS3 server at {host}:{port}",
        error_code=ErrorCode.GNS3_UNREACHABLE.value,
        details=details,
        suggested_action="Check that GNS3 server is running and accessible at the configured host and port",
        context={
            "host": host,
            "port": port
        }
    )


def console_connection_failed_error(
    node_name: str,
    host: str,
    port: int,
    details: str
) -> str:
    """Standard 'console connection failed' error

    Args:
        node_name: Node name
        host: Console host
        port: Console port
        details: Error details

    Returns:
        JSON error response
    """
    from models import ErrorCode

    return create_error_response(
        error=f"Failed to connect to console for node '{node_name}'",
        error_code=ErrorCode.CONSOLE_CONNECTION_FAILED.value,
        details=details,
        suggested_action=f"Verify node '{node_name}' is started and console port {port} is correct",
        context={
            "node_name": node_name,
            "host": host,
            "port": port
        }
    )
