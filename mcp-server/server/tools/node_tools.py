"""Node management tools for GNS3 MCP Server

Provides tools for listing, creating, modifying, and deleting GNS3 nodes.
"""
import asyncio
import json
from typing import TYPE_CHECKING, Optional, Dict, Any

from models import NodeInfo, NodeSummary, ErrorResponse, ErrorCode
from error_utils import (
    create_error_response,
    node_not_found_error,
    project_not_found_error,
    template_not_found_error,
    node_running_error,
    validation_error
)

if TYPE_CHECKING:
    from main import AppContext


async def list_nodes_impl(app: "AppContext") -> str:
    """List all nodes in the current project with basic info (lightweight)

    Returns only essential node information to avoid large outputs.
    Use get_node_details() to retrieve full information for specific nodes.

    Returns:
        JSON array of NodeSummary objects
    """
    try:
        # Get nodes directly from API
        nodes = await app.gns3.get_nodes(app.current_project_id)

        # Convert to NodeSummary models (lightweight)
        node_summaries = []
        for n in nodes:
            node_summaries.append(NodeSummary(
                node_id=n['node_id'],
                name=n['name'],
                node_type=n['node_type'],
                status=n['status'],
                console_type=n['console_type'],
                console=n.get('console')
            ))

        return json.dumps([n.model_dump() for n in node_summaries], indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to list nodes",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and a project is currently open",
            context={"project_id": app.current_project_id, "exception": str(e)}
        )


async def get_node_details_impl(app: "AppContext", node_name: str) -> str:
    """Get detailed information about a specific node

    Args:
        node_name: Name of the node

    Returns:
        JSON with NodeInfo object
    """
    try:
        # Get nodes directly from API
        nodes = await app.gns3.get_nodes(app.current_project_id)

        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            available_nodes = [n['name'] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes
            )

        # Extract hardware properties from nested 'properties' object
        props = node.get('properties', {})

        # Convert to NodeInfo model
        node_info = NodeInfo(
            node_id=node['node_id'],
            name=node['name'],
            node_type=node['node_type'],
            status=node['status'],
            console_type=node['console_type'],
            console=node.get('console'),
            console_host=node.get('console_host'),
            compute_id=node.get('compute_id', 'local'),
            x=node.get('x', 0),
            y=node.get('y', 0),
            z=node.get('z', 0),
            locked=node.get('locked', False),
            ports=node.get('ports'),
            label=node.get('label'),
            symbol=node.get('symbol'),
            # Hardware properties
            ram=props.get('ram'),
            cpus=props.get('cpus'),
            adapters=props.get('adapters'),
            hdd_disk_image=props.get('hdd_disk_image'),
            hda_disk_image=props.get('hda_disk_image')
        )

        return json.dumps(node_info.model_dump(), indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to get details for node '{node_name}'",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Verify the node exists and GNS3 server is accessible",
            context={"node_name": node_name, "project_id": app.current_project_id, "exception": str(e)}
        )


async def set_node_impl(app: "AppContext",
                        node_name: str,
                        action: Optional[str] = None,
                        x: Optional[int] = None,
                        y: Optional[int] = None,
                        z: Optional[int] = None,
                        locked: Optional[bool] = None,
                        ports: Optional[int] = None,
                        name: Optional[str] = None,
                        ram: Optional[int] = None,
                        cpus: Optional[int] = None,
                        hdd_disk_image: Optional[str] = None,
                        adapters: Optional[int] = None,
                        console_type: Optional[str] = None) -> str:
    """Configure node properties and/or control node state

    Validation Rules:
    - name parameter requires node to be stopped
    - Hardware properties (ram, cpus, hdd_disk_image, adapters) apply to QEMU nodes only
    - ports parameter applies to ethernet_switch nodes only
    - action values: start, stop, suspend, reload, restart
    - restart action: stops node (with retry logic), waits for confirmed stop, then starts

    Args:
        node_name: Name of the node to modify
        action: Action to perform (start/stop/suspend/reload/restart)
        x: X coordinate (top-left corner of node icon)
        y: Y coordinate (top-left corner of node icon)
        z: Z-order (layer) for overlapping nodes
        locked: Lock node position (prevents accidental moves in GUI)
        ports: Number of ports (ethernet_switch nodes only)
        name: New name for the node (REQUIRES node to be stopped)
        ram: RAM in MB (QEMU nodes only)
        cpus: Number of CPUs (QEMU nodes only)
        hdd_disk_image: Path to HDD disk image (QEMU nodes only)
        adapters: Number of network adapters (QEMU nodes only)
        console_type: Console type - telnet, vnc, spice, etc.

    Returns:
        Status message describing what was done
    """
    if not app.current_project_id:
        return project_not_found_error()

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        available_nodes = [n['name'] for n in nodes]
        return node_not_found_error(
            node_name=node_name,
            project_id=app.current_project_id,
            available_nodes=available_nodes
        )

    node_id = node['node_id']
    node_status = node.get('status', 'unknown')
    results = []

    # Validate stopped state for properties that require it
    requires_stopped = []
    if name is not None:
        requires_stopped.append('name')

    if requires_stopped and node_status != 'stopped':
        properties_str = ', '.join(requires_stopped)
        return node_running_error(
            node_name=node_name,
            operation=f"change properties: {properties_str}"
        )

    # Handle property updates
    # Separate top-level properties from hardware properties
    update_payload = {}
    hardware_props = {}

    # Top-level properties
    if x is not None:
        update_payload['x'] = x
    if y is not None:
        update_payload['y'] = y
    if z is not None:
        update_payload['z'] = z
    if locked is not None:
        update_payload['locked'] = locked
    if name is not None:
        update_payload['name'] = name

    # Hardware properties (nested in 'properties' object for QEMU nodes)
    if ram is not None:
        hardware_props['ram'] = ram
    if cpus is not None:
        hardware_props['cpus'] = cpus
    if hdd_disk_image is not None:
        hardware_props['hdd_disk_image'] = hdd_disk_image
    if adapters is not None:
        hardware_props['adapters'] = adapters
    if console_type is not None:
        hardware_props['console_type'] = console_type

    # Special handling for ethernet switches
    if ports is not None:
        if node['node_type'] == 'ethernet_switch':
            ports_mapping = [
                {"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1}
                for i in range(ports)
            ]
            hardware_props['ports_mapping'] = ports_mapping
        else:
            results.append(f"Warning: Port configuration only supported for ethernet switches")

    # Wrap hardware properties in 'properties' object for QEMU nodes
    if hardware_props and node['node_type'] == 'qemu':
        update_payload['properties'] = hardware_props
    elif hardware_props:
        # For non-QEMU nodes, merge directly
        update_payload.update(hardware_props)

    if update_payload:
        try:
            await app.gns3.update_node(app.current_project_id, node_id, update_payload)

            # Build change summary
            changes = []
            if name is not None:
                changes.append(f"name={name}")
            if x is not None or y is not None or z is not None:
                pos_parts = []
                if x is not None: pos_parts.append(f"x={x}")
                if y is not None: pos_parts.append(f"y={y}")
                if z is not None: pos_parts.append(f"z={z}")
                changes.append(", ".join(pos_parts))
            if locked is not None:
                changes.append(f"locked={locked}")
            for k, v in hardware_props.items():
                if k != 'ports_mapping':
                    changes.append(f"{k}={v}")
            if 'ports_mapping' in hardware_props:
                changes.append(f"ports={ports}")

            results.append(f"Updated: {', '.join(changes)}")
        except Exception as e:
            return create_error_response(
                error=f"Failed to update properties for node '{node_name}'",
                error_code=ErrorCode.OPERATION_FAILED.value,
                details=str(e),
                suggested_action="Check that the property values are valid for this node type and GNS3 server is accessible",
                context={"node_name": node_name, "update_payload": update_payload, "exception": str(e)}
            )

    # Handle action
    if action:
        action = action.lower()
        try:
            if action == 'start':
                await app.gns3.start_node(app.current_project_id, node_id)
                results.append(f"Started {node_name}")

            elif action == 'stop':
                await app.gns3.stop_node(app.current_project_id, node_id)
                results.append(f"Stopped {node_name}")

            elif action == 'suspend':
                await app.gns3.suspend_node(app.current_project_id, node_id)
                results.append(f"Suspended {node_name}")

            elif action == 'reload':
                await app.gns3.reload_node(app.current_project_id, node_id)
                results.append(f"Reloaded {node_name}")

            elif action == 'restart':
                # Stop node
                await app.gns3.stop_node(app.current_project_id, node_id)
                results.append(f"Stopped {node_name}")

                # Wait for node to stop with retries
                stopped = False
                for attempt in range(3):
                    await asyncio.sleep(5)
                    nodes = await app.gns3.get_nodes(app.current_project_id)
                    current_node = next((n for n in nodes if n['node_id'] == node_id), None)
                    if current_node and current_node['status'] == 'stopped':
                        stopped = True
                        break
                    results.append(f"Retry {attempt + 1}/3: Waiting for stop...")

                if not stopped:
                    results.append(f"Warning: Node may not have stopped completely")

                # Start node
                await app.gns3.start_node(app.current_project_id, node_id)
                results.append(f"Started {node_name}")

            else:
                return validation_error(
                    message=f"Invalid action '{action}'",
                    parameter="action",
                    value=action,
                    valid_values=["start", "stop", "suspend", "reload", "restart"]
                )

        except Exception as e:
            return create_error_response(
                error=f"Failed to execute action '{action}' on node '{node_name}'",
                error_code=ErrorCode.OPERATION_FAILED.value,
                details=str(e),
                suggested_action="Check node state and GNS3 server logs for details",
                context={"node_name": node_name, "action": action, "exception": str(e)}
            )

    if not results:
        return json.dumps({"message": f"No changes made to {node_name}"}, indent=2)

    # Return success with list of changes
    return json.dumps({"message": "Node updated successfully", "changes": results}, indent=2)


async def create_node_impl(app: "AppContext", template_name: str, x: int, y: int,
                           node_name: Optional[str] = None, compute_id: str = "local",
                           properties: Optional[Dict[str, Any]] = None) -> str:
    """Create a new node from a template

    Args:
        template_name: Name of the template to use
        x: X coordinate position (top-left corner of node icon)
        y: Y coordinate position (top-left corner of node icon)
        node_name: Optional custom name for the node
        compute_id: Compute ID (default: "local")
        properties: Optional dict to override template properties

    Note: Coordinates represent the top-left corner of the node icon.
    Icon sizes are PNG: 78×78, SVG/internal: 58×58.

    Returns:
        JSON with created NodeInfo
    """
    try:
        templates = await app.gns3.get_templates()
        template = next((t for t in templates if t['name'] == template_name), None)

        if not template:
            available_templates = [t['name'] for t in templates]
            return template_not_found_error(
                template_name=template_name,
                available_templates=available_templates
            )

        payload = {"x": x, "y": y, "compute_id": compute_id}
        if node_name:
            payload["name"] = node_name
        if properties:
            payload["properties"] = properties

        result = await app.gns3.create_node_from_template(
            app.current_project_id, template['template_id'], payload
        )

        return json.dumps({"message": "Node created successfully", "node": result}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to create node from template '{template_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify template exists, GNS3 server is accessible, and position coordinates are valid",
            context={"template_name": template_name, "x": x, "y": y, "node_name": node_name, "exception": str(e)}
        )


async def delete_node_impl(app: "AppContext", node_name: str) -> str:
    """Delete a node from the current project

    Args:
        node_name: Name of the node to delete

    Returns:
        JSON confirmation message
    """
    try:
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            available_nodes = [n['name'] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes
            )

        await app.gns3.delete_node(app.current_project_id, node['node_id'])

        return json.dumps({"message": f"Node '{node_name}' deleted successfully"}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to delete node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify the node exists, stop it if running, and check GNS3 server is accessible",
            context={"node_name": node_name, "project_id": app.current_project_id, "exception": str(e)}
        )


async def get_node_file_impl(app: "AppContext", node_name: str, file_path: str) -> str:
    """Read file from Docker node filesystem

    Args:
        node_name: Name of the node
        file_path: Path relative to container root (e.g., 'etc/network/interfaces')

    Returns:
        JSON with file contents
    """
    if not app.current_project_id:
        return project_not_found_error()

    try:
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            available_nodes = [n['name'] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes
            )

        # Validate node type
        if node['node_type'] != 'docker':
            return create_error_response(
                error=f"File operations only supported for Docker nodes",
                error_code=ErrorCode.INVALID_OPERATION.value,
                details=f"Node '{node_name}' is type '{node['node_type']}', expected 'docker'",
                suggested_action="Only Docker nodes support file read/write operations",
                context={"node_name": node_name, "node_type": node['node_type']}
            )

        content = await app.gns3.get_node_file(app.current_project_id, node['node_id'], file_path)

        return json.dumps({
            "node_name": node_name,
            "file_path": file_path,
            "content": content
        }, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to read file '{file_path}' from node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check that the file path is correct and the node is a Docker container",
            context={"node_name": node_name, "file_path": file_path, "exception": str(e)}
        )


async def write_node_file_impl(app: "AppContext", node_name: str, file_path: str, content: str) -> str:
    """Write file to Docker node filesystem

    Note: File changes do NOT automatically restart the node or apply configuration.
    For network configuration, use configure_node_network() which handles the full workflow.

    Args:
        node_name: Name of the node
        file_path: Path relative to container root (e.g., 'etc/network/interfaces')
        content: File contents to write

    Returns:
        JSON confirmation message
    """
    if not app.current_project_id:
        return project_not_found_error()

    try:
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            available_nodes = [n['name'] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes
            )

        # Validate node type
        if node['node_type'] != 'docker':
            return create_error_response(
                error=f"File operations only supported for Docker nodes",
                error_code=ErrorCode.INVALID_OPERATION.value,
                details=f"Node '{node_name}' is type '{node['node_type']}', expected 'docker'",
                suggested_action="Only Docker nodes support file read/write operations",
                context={"node_name": node_name, "node_type": node['node_type']}
            )

        await app.gns3.write_node_file(app.current_project_id, node['node_id'], file_path, content)

        return json.dumps({
            "message": f"File '{file_path}' written successfully to node '{node_name}'",
            "node_name": node_name,
            "file_path": file_path,
            "note": "Node restart may be required for changes to take effect"
        }, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to write file '{file_path}' to node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check that the file path is valid and the node is a Docker container",
            context={"node_name": node_name, "file_path": file_path, "exception": str(e)}
        )


async def configure_node_network_impl(app: "AppContext", node_name: str, interfaces: list[Dict[str, Any]]) -> str:
    """Configure network interfaces on Docker node

    Generates /etc/network/interfaces file and restarts the node to apply configuration.
    Supports both static IP and DHCP configuration for multiple interfaces.

    Args:
        node_name: Name of the node
        interfaces: List of interface configurations, each with:
            - name: Interface name (eth0, eth1, etc.)
            - mode: "static" or "dhcp"
            - address: IP address (static mode only)
            - netmask: Network mask (static mode only)
            - gateway: Default gateway (static mode, optional)
            - dns: DNS server IP (optional, default: 8.8.8.8)

    Returns:
        JSON confirmation with configured interfaces
    """
    if not app.current_project_id:
        return project_not_found_error()

    try:
        from models import NetworkConfig, NetworkInterfaceStatic, NetworkInterfaceDHCP

        # Validate and parse interfaces
        parsed_interfaces = []
        for iface_dict in interfaces:
            if iface_dict.get('mode') == 'static':
                parsed_interfaces.append(NetworkInterfaceStatic(**iface_dict))
            elif iface_dict.get('mode') == 'dhcp':
                parsed_interfaces.append(NetworkInterfaceDHCP(**iface_dict))
            else:
                return validation_error(
                    field="interfaces[].mode",
                    message=f"Invalid mode '{iface_dict.get('mode')}', must be 'static' or 'dhcp'"
                )

        config = NetworkConfig(interfaces=parsed_interfaces)

        # Generate interfaces file content
        interfaces_content = config.to_debian_interfaces()

        # Get node
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node = next((n for n in nodes if n['name'] == node_name), None)

        if not node:
            available_nodes = [n['name'] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes
            )

        # Validate node type
        if node['node_type'] != 'docker':
            return create_error_response(
                error=f"Network configuration only supported for Docker nodes",
                error_code=ErrorCode.INVALID_OPERATION.value,
                details=f"Node '{node_name}' is type '{node['node_type']}', expected 'docker'",
                suggested_action="Only Docker nodes support network configuration",
                context={"node_name": node_name, "node_type": node['node_type']}
            )

        # Write interfaces file
        await app.gns3.write_node_file(
            app.current_project_id,
            node['node_id'],
            'etc/network/interfaces',
            interfaces_content
        )

        # Restart node to apply configuration
        # Note: Using restart action which stops with retry logic then starts
        await app.gns3.stop_node(app.current_project_id, node['node_id'])

        # Wait for confirmed stop
        for _ in range(10):  # Try up to 10 times
            await asyncio.sleep(1)
            nodes = await app.gns3.get_nodes(app.current_project_id)
            node = next((n for n in nodes if n['node_id'] == node['node_id']), None)
            if node and node['status'] == 'stopped':
                break

        # Start node
        await app.gns3.start_node(app.current_project_id, node['node_id'])

        return json.dumps({
            "message": f"Network configuration applied to node '{node_name}'",
            "node_name": node_name,
            "interfaces": [iface.model_dump() for iface in config.interfaces],
            "status": "Node restarted to apply configuration",
            "note": "Allow 10-15 seconds for node to complete startup and network configuration"
        }, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to configure network on node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check interface configuration parameters and verify node is accessible",
            context={"node_name": node_name, "interfaces": interfaces, "exception": str(e)}
        )
