"""Node management tools for GNS3 MCP Server

Provides tools for listing, creating, modifying, and deleting GNS3 nodes.
"""
import asyncio
import json
from typing import TYPE_CHECKING, Optional

from models import NodeInfo, ErrorResponse

if TYPE_CHECKING:
    from main import AppContext


async def list_nodes_impl(app: "AppContext") -> str:
    """List all nodes in the current project with their status and console info

    Returns:
        JSON array of NodeInfo objects
    """
    try:
        # Get nodes directly from API
        nodes = await app.gns3.get_nodes(app.current_project_id)

        # Convert to NodeInfo models
        node_models = []
        for n in nodes:
            props = n.get('properties', {})
            node_models.append(NodeInfo(
                node_id=n['node_id'],
                name=n['name'],
                node_type=n['node_type'],
                status=n['status'],
                console_type=n['console_type'],
                console=n.get('console'),
                console_host=n.get('console_host'),
                compute_id=n.get('compute_id', 'local'),
                x=n.get('x', 0),
                y=n.get('y', 0),
                z=n.get('z', 0),
                locked=n.get('locked', False),
                ports=n.get('ports'),
                label=n.get('label'),
                symbol=n.get('symbol'),
                # Hardware properties
                ram=props.get('ram'),
                cpus=props.get('cpus'),
                adapters=props.get('adapters'),
                hdd_disk_image=props.get('hdd_disk_image'),
                hda_disk_image=props.get('hda_disk_image')
            ))

        return json.dumps([n.model_dump() for n in node_models], indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list nodes",
            details=str(e)
        ).model_dump(), indent=2)


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
            return json.dumps(ErrorResponse(
                error="Node not found",
                details=f"No node named '{node_name}' in current project. Use list_nodes() to see available nodes.",
                suggested_action="Call list_nodes() to see exact node names (case-sensitive)"
            ).model_dump(), indent=2)

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
        return json.dumps(ErrorResponse(
            error="Failed to get node details",
            details=str(e)
        ).model_dump(), indent=2)


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
        return json.dumps(ErrorResponse(
            error="No project opened",
            details="Use open_project() to open a project first"
        ).model_dump(), indent=2)

    # Find node
    nodes = await app.gns3.get_nodes(app.current_project_id)
    node = next((n for n in nodes if n['name'] == node_name), None)

    if not node:
        return json.dumps(ErrorResponse(
            error="Node not found",
            details=f"Node '{node_name}' does not exist in current project",
            suggested_action="Call list_nodes() to see exact node names (case-sensitive)"
        ).model_dump(), indent=2)

    node_id = node['node_id']
    node_status = node.get('status', 'unknown')
    results = []

    # Validate stopped state for properties that require it
    requires_stopped = []
    if name is not None:
        requires_stopped.append('name')

    if requires_stopped and node_status != 'stopped':
        return json.dumps(ErrorResponse(
            error="Node must be stopped",
            details=f"Properties {requires_stopped} can only be changed when node is stopped. Current status: {node_status}. Use set_node(node_name='{node_name}', action='stop') first."
        ).model_dump(), indent=2)

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
            return json.dumps(ErrorResponse(
                error="Failed to update properties",
                details=str(e)
            ).model_dump(), indent=2)

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
                return json.dumps(ErrorResponse(
                    error="Unknown action",
                    details=f"Action '{action}' not recognized. Valid actions: start, stop, suspend, reload, restart"
                ).model_dump(), indent=2)

        except Exception as e:
            return json.dumps(ErrorResponse(
                error="Action failed",
                details=str(e)
            ).model_dump(), indent=2)

    if not results:
        return json.dumps({"message": f"No changes made to {node_name}"}, indent=2)

    # Return success with list of changes
    return json.dumps({"message": "Node updated successfully", "changes": results}, indent=2)


async def create_node_impl(app: "AppContext", template_name: str, x: int, y: int,
                           node_name: Optional[str] = None, compute_id: str = "local") -> str:
    """Create a new node from a template

    Args:
        template_name: Name of the template to use
        x: X coordinate position (top-left corner of node icon)
        y: Y coordinate position (top-left corner of node icon)
        node_name: Optional custom name for the node
        compute_id: Compute ID (default: "local")

    Note: Coordinates represent the top-left corner of the node icon.
    Icon sizes are PNG: 78×78, SVG/internal: 58×58.

    Returns:
        JSON with created NodeInfo
    """
    try:
        templates = await app.gns3.get_templates()
        template = next((t for t in templates if t['name'] == template_name), None)

        if not template:
            return json.dumps(ErrorResponse(
                error="Template not found",
                details=f"Template '{template_name}' not found. Use list_templates() to see available templates."
            ).model_dump(), indent=2)

        payload = {"x": x, "y": y, "compute_id": compute_id}
        if node_name:
            payload["name"] = node_name

        result = await app.gns3.create_node_from_template(
            app.current_project_id, template['template_id'], payload
        )

        return json.dumps({"message": "Node created successfully", "node": result}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to create node",
            details=str(e)
        ).model_dump(), indent=2)


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
            return json.dumps(ErrorResponse(
                error="Node not found",
                details=f"Node '{node_name}' does not exist"
            ).model_dump(), indent=2)

        await app.gns3.delete_node(app.current_project_id, node['node_id'])

        return json.dumps({"message": f"Node '{node_name}' deleted successfully"}, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to delete node",
            details=str(e)
        ).model_dump(), indent=2)
