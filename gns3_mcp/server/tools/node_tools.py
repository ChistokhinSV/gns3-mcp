"""Node management tools for GNS3 MCP Server

Provides tools for listing, creating, modifying, and deleting GNS3 nodes.
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List

import httpx
from error_utils import (
    create_error_response,
    node_not_found_error,
    project_not_found_error,
    template_not_found_error,
    validation_error,
)
from fastmcp import Context
from models import ErrorCode, NodeInfo, NodeSummary

if TYPE_CHECKING:
    from interfaces import IAppContext, IGns3Client

logger = logging.getLogger(__name__)

# SSH Proxy API URL (defaults to GNS3 host IP)
_gns3_host = os.getenv("GNS3_HOST", "localhost")
SSH_PROXY_URL = os.getenv("SSH_PROXY_URL", f"http://{_gns3_host}:8022")


# v0.40.0: Wildcard and bulk operations support


class BatchOperationResult:
    """Track results of batch operations with per-item success/failure/skip tracking.

    Used for bulk node operations to provide detailed feedback on each item.
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.succeeded: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.start_time = time.time()

    def add_success(self, item: str, details: Dict | None = None):
        """Record successful operation on item."""
        self.succeeded.append({"item": item, "details": details or {}})

    def add_failure(self, item: str, error: str, suggestion: str | None = None):
        """Record failed operation on item."""
        self.failed.append(
            {
                "item": item,
                "error": error,
                "suggestion": suggestion or "Check item configuration and try again",
            }
        )

    def add_skip(self, item: str, reason: str):
        """Record skipped item."""
        self.skipped.append({"item": item, "reason": reason})

    def add_warning(self, warning: str):
        """Add warning message."""
        self.warnings.append(warning)

    def to_json(self) -> str:
        """Convert to JSON string with summary and details."""
        elapsed = time.time() - self.start_time
        total = len(self.succeeded) + len(self.failed) + len(self.skipped)

        # Determine overall status
        if not self.failed and not self.skipped:
            status = "success"
        elif self.succeeded and self.failed:
            status = "partial_success"
        elif not self.succeeded and self.failed:
            status = "failure"
        else:
            status = "success"  # Only skipped items

        return json.dumps(
            {
                "operation": self.operation_name,
                "status": status,
                "summary": {
                    "total_items": total,
                    "succeeded": len(self.succeeded),
                    "failed": len(self.failed),
                    "skipped": len(self.skipped),
                    "elapsed_seconds": round(elapsed, 2),
                },
                "succeeded_items": self.succeeded,
                "failed_items": self.failed,
                "skipped_items": self.skipped,
                "warnings": self.warnings,
            },
            indent=2,
        )


def match_node_pattern(pattern: str, node_name: str) -> bool:
    """Check if node name matches wildcard pattern.

    Supports:
    - Exact match: "Router1"
    - Wildcard all: "*"
    - Prefix match: "Router*" (matches Router1, Router2, RouterCore)
    - Suffix match: "*-Core" (matches Router-Core, Switch-Core)
    - Contains match: "*Router*" (matches MyRouter1, TestRouter)
    - Character class: "R[123]" (matches R1, R2, R3)

    Args:
        pattern: Wildcard pattern
        node_name: Node name to test

    Returns:
        True if node name matches pattern
    """
    # Wildcard all
    if pattern == "*":
        return True

    # Convert shell-style wildcard to regex
    # Escape special regex characters except * and []
    regex_pattern = re.escape(pattern)
    # Replace escaped \* with .*
    regex_pattern = regex_pattern.replace(r"\*", ".*")
    # Unescape [] for character classes
    regex_pattern = regex_pattern.replace(r"\[", "[").replace(r"\]", "]")

    # Match full string
    regex_pattern = f"^{regex_pattern}$"

    return bool(re.match(regex_pattern, node_name, re.IGNORECASE))


def resolve_node_names(node_spec: str, all_nodes: List[Dict[str, Any]]) -> List[str]:
    """Resolve node specification to list of node names.

    Supports:
    - Single node: "Router1"
    - Wildcard all: "*"
    - Pattern match: "Router*", "*-Core", "R[123]"
    - JSON array: '["Router1", "Router2", "Switch1"]'

    Args:
        node_spec: Node specification (name, pattern, or JSON array)
        all_nodes: List of all nodes in project

    Returns:
        List of matching node names (empty if no matches)
    """
    # Try parsing as JSON array
    try:
        parsed = json.loads(node_spec)
        if isinstance(parsed, list):
            # Return only nodes that exist
            all_node_names = {n["name"] for n in all_nodes}
            return [name for name in parsed if name in all_node_names]
    except (json.JSONDecodeError, TypeError):
        pass

    # Wildcard or pattern matching
    if "*" in node_spec or "[" in node_spec:
        matching_nodes = [n["name"] for n in all_nodes if match_node_pattern(node_spec, n["name"])]
        return matching_nodes

    # Single node name (exact match, case-sensitive)
    if any(n["name"] == node_spec for n in all_nodes):
        return [node_spec]

    # No matches
    return []


async def list_nodes_impl(app: "IAppContext") -> str:
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
            node_summaries.append(
                NodeSummary(
                    node_id=n["node_id"],
                    name=n["name"],
                    node_type=n["node_type"],
                    status=n["status"],
                    console_type=n["console_type"],
                    console=n.get("console"),
                )
            )

        return json.dumps([n.model_dump() for n in node_summaries], indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to list nodes",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and a project is currently open",
            context={"project_id": app.current_project_id, "exception": str(e)},
        )


async def get_node_details_impl(app: "IAppContext", node_name: str) -> str:
    """Get detailed information about a specific node

    Args:
        node_name: Name of the node

    Returns:
        JSON with NodeInfo object
    """
    try:
        # Get nodes directly from API
        nodes = await app.gns3.get_nodes(app.current_project_id)

        node = next((n for n in nodes if n["name"] == node_name), None)

        if not node:
            available_nodes = [n["name"] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes,
            )

        # Extract hardware properties from nested 'properties' object
        props = node.get("properties", {})

        # Convert to NodeInfo model
        node_info = NodeInfo(
            node_id=node["node_id"],
            name=node["name"],
            node_type=node["node_type"],
            status=node["status"],
            console_type=node["console_type"],
            console=node.get("console"),
            console_host=node.get("console_host"),
            compute_id=node.get("compute_id", "local"),
            x=node.get("x", 0),
            y=node.get("y", 0),
            z=node.get("z", 0),
            locked=node.get("locked", False),
            ports=node.get("ports"),
            label=node.get("label"),
            symbol=node.get("symbol"),
            # Hardware properties
            ram=props.get("ram"),
            cpus=props.get("cpus"),
            adapters=props.get("adapters"),
            hdd_disk_image=props.get("hdd_disk_image"),
            hda_disk_image=props.get("hda_disk_image"),
        )

        return json.dumps(node_info.model_dump(), indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to get details for node '{node_name}'",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Verify the node exists and GNS3 server is accessible",
            context={
                "node_name": node_name,
                "project_id": app.current_project_id,
                "exception": str(e),
            },
        )


async def _set_single_node_impl(
    app: "IAppContext",
    node: Dict[str, Any],
    action: str | None = None,
    x: int | None = None,
    y: int | None = None,
    z: int | None = None,
    locked: bool | None = None,
    ports: int | None = None,
    name: str | None = None,
    ram: int | None = None,
    cpus: int | None = None,
    hdd_disk_image: str | None = None,
    adapters: int | None = None,
    console_type: str | None = None,
    ctx: Context | None = None,
) -> List[str]:
    """Perform set_node operation on a single node.

    Internal helper function extracted from set_node_impl to support bulk operations.

    Returns:
        List of result messages (not JSON)

    Raises:
        Exception on failures (caught by caller)
    """
    node_name = node["name"]
    node_id = node["node_id"]
    node_status = node.get("status", "unknown")
    node_type = node.get("node_type", "")
    results = []

    # Stateless built-in devices that can be renamed without stopping
    STATELESS_DEVICES = {
        "ethernet_switch",
        "ethernet_hub",
        "atm_switch",
        "frame_relay_switch",
        "cloud",
        "nat",
    }

    # Validate stopped state for properties that require it
    requires_stopped = []
    if name is not None:
        # Stateless devices don't need to be stopped for renaming
        if node_type not in STATELESS_DEVICES:
            requires_stopped.append("name")

    if requires_stopped and node_status != "stopped":
        raise ValueError(f"Node must be stopped to change: {', '.join(requires_stopped)}")

    # Handle property updates
    update_payload = {}
    hardware_props = {}

    # Top-level properties
    if x is not None:
        update_payload["x"] = x
    if y is not None:
        update_payload["y"] = y
    if z is not None:
        update_payload["z"] = z
    if locked is not None:
        update_payload["locked"] = locked
    if name is not None:
        update_payload["name"] = name

    # Hardware properties
    if ram is not None:
        hardware_props["ram"] = ram
    if cpus is not None:
        hardware_props["cpus"] = cpus
    if hdd_disk_image is not None:
        hardware_props["hdd_disk_image"] = hdd_disk_image
    if adapters is not None:
        hardware_props["adapters"] = adapters
    if console_type is not None:
        hardware_props["console_type"] = console_type

    # Special handling for ethernet switches
    if ports is not None:
        if node["node_type"] == "ethernet_switch":
            ports_mapping = [
                {"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1}
                for i in range(ports)
            ]
            hardware_props["ports_mapping"] = ports_mapping
        else:
            results.append("Warning: Port configuration only supported for ethernet switches")

    # Wrap hardware properties in 'properties' object for QEMU nodes
    if hardware_props and node["node_type"] == "qemu":
        update_payload["properties"] = hardware_props
    elif hardware_props:
        update_payload.update(hardware_props)

    if update_payload:
        await app.gns3.update_node(app.current_project_id, node_id, update_payload)

        # Build change summary
        changes = []
        if name is not None:
            changes.append(f"name={name}")
        if x is not None or y is not None or z is not None:
            pos_parts = []
            if x is not None:
                pos_parts.append(f"x={x}")
            if y is not None:
                pos_parts.append(f"y={y}")
            if z is not None:
                pos_parts.append(f"z={z}")
            changes.append(", ".join(pos_parts))
        if locked is not None:
            changes.append(f"locked={locked}")
        for k, v in hardware_props.items():
            if k != "ports_mapping":
                changes.append(f"{k}={v}")
        if "ports_mapping" in hardware_props:
            changes.append(f"ports={ports}")

        results.append(f"Updated: {', '.join(changes)}")

    # Handle action
    if action:
        action_lower = action.lower()

        if action_lower == "start":
            await app.gns3.start_node(app.current_project_id, node_id)

            # Poll for startup completion with progress notifications (v0.39.0)
            max_steps = 12
            for step in range(max_steps):
                if ctx:
                    await ctx.report_progress(
                        progress=step,
                        total=max_steps,
                        message=f"Starting {node_name}... (step {step + 1}/{max_steps})",
                    )

                nodes = await app.gns3.get_nodes(app.current_project_id)
                current_node = next((n for n in nodes if n["node_id"] == node_id), None)

                if current_node and current_node.get("status") == "started":
                    if ctx:
                        await ctx.report_progress(
                            progress=max_steps,
                            total=max_steps,
                            message=f"{node_name} started successfully",
                        )
                    results.append(f"Started (ready after {(step + 1) * 5}s)")
                    break

                if step < max_steps - 1:
                    await asyncio.sleep(5)
            else:
                results.append("Started (startup in progress)")

        elif action_lower == "stop":
            await app.gns3.stop_node(app.current_project_id, node_id)
            results.append("Stopped")

        elif action_lower == "suspend":
            await app.gns3.suspend_node(app.current_project_id, node_id)
            results.append("Suspended")

        elif action_lower == "reload":
            await app.gns3.reload_node(app.current_project_id, node_id)
            results.append("Reloaded")

        elif action_lower == "restart":
            await app.gns3.stop_node(app.current_project_id, node_id)
            results.append("Stopped")

            # Wait for stop confirmation
            stopped = False
            for attempt in range(3):
                await asyncio.sleep(5)
                nodes = await app.gns3.get_nodes(app.current_project_id)
                current_node = next((n for n in nodes if n["node_id"] == node_id), None)
                if current_node and current_node["status"] == "stopped":
                    stopped = True
                    break

            if not stopped:
                results.append("Warning: Node may not have stopped completely")

            await app.gns3.start_node(app.current_project_id, node_id)
            results.append("Started")

        else:
            raise ValueError(
                f"Invalid action '{action}'. Valid: start, stop, suspend, reload, restart"
            )

    return results


async def set_node_impl(
    app: "IAppContext",
    node_name: str,
    action: str | None = None,
    x: int | None = None,
    y: int | None = None,
    z: int | None = None,
    locked: bool | None = None,
    ports: int | None = None,
    name: str | None = None,
    ram: int | None = None,
    cpus: int | None = None,
    hdd_disk_image: str | None = None,
    adapters: int | None = None,
    console_type: str | None = None,
    ctx: Context | None = None,
    parallel: bool = True,
) -> str:
    """Configure node properties and/or control node state.

    v0.40.0: Enhanced with wildcard and bulk operation support.

    Wildcard Patterns:
    - Single node: "Router1"
    - All nodes: "*"
    - Prefix match: "Router*" (matches Router1, Router2, RouterCore)
    - Suffix match: "*-Core" (matches Router-Core, Switch-Core)
    - Character class: "R[123]" (matches R1, R2, R3)
    - JSON array: '["Router1", "Router2", "Switch1"]'

    Validation Rules:
    - name parameter requires node to be stopped (except for stateless devices)
    - Stateless devices can be renamed while running: ethernet_switch, ethernet_hub,
      atm_switch, frame_relay_switch, cloud, nat
    - Hardware properties (ram, cpus, hdd_disk_image, adapters) apply to QEMU nodes only
    - ports parameter applies to ethernet_switch nodes only
    - action values: start, stop, suspend, reload, restart
    - restart action: stops node (with retry logic), waits for confirmed stop, then starts

    Args:
        node_name: Node name, wildcard pattern, or JSON array of names
        action: Action to perform (start/stop/suspend/reload/restart)
        x: X coordinate (top-left corner of node icon)
        y: Y coordinate (top-left corner of node icon)
        z: Z-order (layer) for overlapping nodes
        locked: Lock node position (prevents accidental moves in GUI)
        ports: Number of ports (ethernet_switch nodes only)
        name: New name for the node (requires stop for QEMU/Docker)
        ram: RAM in MB (QEMU nodes only)
        cpus: Number of CPUs (QEMU nodes only)
        hdd_disk_image: Path to HDD disk image (QEMU nodes only)
        adapters: Number of network adapters (QEMU nodes only)
        console_type: Console type - telnet, vnc, spice, etc.
        parallel: Execute operations concurrently (default: True for start/stop actions)

    Returns:
        For single node: Status message (backward compatible)
        For multiple nodes: BatchOperationResult JSON with per-node results
    """
    if not app.current_project_id:
        return project_not_found_error()

    # Get all nodes
    nodes = await app.gns3.get_nodes(app.current_project_id)

    # Resolve node names
    resolved_names = resolve_node_names(node_name, nodes)

    # Handle no matches
    if not resolved_names:
        available_nodes = [n["name"] for n in nodes]
        return node_not_found_error(
            node_name=node_name, project_id=app.current_project_id, available_nodes=available_nodes
        )

    # Single node - backward compatible response
    if len(resolved_names) == 1 and not ("*" in node_name or "[" in node_name):
        node = next((n for n in nodes if n["name"] == resolved_names[0]), None)
        if not node:
            return node_not_found_error(
                node_name=resolved_names[0],
                project_id=app.current_project_id,
                available_nodes=[n["name"] for n in nodes],
            )

        try:
            results = await _set_single_node_impl(
                app,
                node,
                action,
                x,
                y,
                z,
                locked,
                ports,
                name,
                ram,
                cpus,
                hdd_disk_image,
                adapters,
                console_type,
                ctx,
            )

            if not results:
                return json.dumps({"message": f"No changes made to {resolved_names[0]}"}, indent=2)

            return json.dumps(
                {"message": "Node updated successfully", "changes": results}, indent=2
            )

        except ValueError as e:
            return validation_error(message=str(e), parameter="node_state")
        except Exception as e:
            return create_error_response(
                error=f"Failed to update node '{resolved_names[0]}'",
                error_code=ErrorCode.OPERATION_FAILED.value,
                details=str(e),
                suggested_action="Check node state and GNS3 server logs",
                context={"node_name": resolved_names[0], "exception": str(e)},
            )

    # Multiple nodes - bulk operation with BatchOperationResult
    result = BatchOperationResult(f"set_node_properties ({action or 'update'})")

    # Filter nodes to process
    nodes_to_process = [n for n in nodes if n["name"] in resolved_names]

    # Determine if parallel execution makes sense
    use_parallel = parallel and action and action.lower() in ["start", "stop", "suspend"]

    if use_parallel:
        # Parallel execution
        tasks = []
        for node in nodes_to_process:
            tasks.append(
                _set_single_node_impl(
                    app,
                    node,
                    action,
                    x,
                    y,
                    z,
                    locked,
                    ports,
                    name,
                    ram,
                    cpus,
                    hdd_disk_image,
                    adapters,
                    console_type,
                    None,  # No ctx for parallel
                )
            )

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for node, res in zip(nodes_to_process, results_list, strict=True):
            if isinstance(res, Exception):
                result.add_failure(
                    node["name"], str(res), suggestion="Check node state and permissions"
                )
            else:
                result.add_success(node["name"], {"changes": res})
    else:
        # Sequential execution
        for node in nodes_to_process:
            try:
                node_results = await _set_single_node_impl(
                    app,
                    node,
                    action,
                    x,
                    y,
                    z,
                    locked,
                    ports,
                    name,
                    ram,
                    cpus,
                    hdd_disk_image,
                    adapters,
                    console_type,
                    ctx,
                )
                result.add_success(node["name"], {"changes": node_results})
            except ValueError as e:
                result.add_failure(node["name"], str(e), suggestion="Check validation requirements")
            except Exception as e:
                result.add_failure(node["name"], str(e), suggestion="Check GNS3 server logs")

    return result.to_json()


async def create_node_impl(
    gns3: "IGns3Client",
    current_project_id: str,
    template_name: str,
    x: int,
    y: int,
    node_name: str | None = None,
    compute_id: str = "local",
    properties: Dict[str, Any] | None = None,
) -> str:
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
        templates = await gns3.get_templates()
        template = next((t for t in templates if t["name"] == template_name), None)

        if not template:
            available_templates = [t["name"] for t in templates]
            return template_not_found_error(
                template_name=template_name, available_templates=available_templates
            )

        payload = {"x": x, "y": y, "compute_id": compute_id}
        if node_name:
            payload["name"] = node_name.strip()  # Strip whitespace
        if properties:
            payload["properties"] = properties

        result = await gns3.create_node_from_template(
            current_project_id, template["template_id"], payload
        )

        # Workaround: If custom name was provided but API ignored it, rename the node
        if node_name:
            requested_name = node_name.strip()
            actual_name = result.get("name", "")

            if actual_name != requested_name:
                # Node was created with wrong name, rename it
                node_id = result["node_id"]
                node_status = result.get("status", "stopped")
                node_type = result.get("node_type", "")

                # Stateless devices can be renamed without stopping
                STATELESS_DEVICES = {
                    "ethernet_switch",
                    "ethernet_hub",
                    "atm_switch",
                    "frame_relay_switch",
                    "cloud",
                    "nat",
                }

                # Check if we need to stop the node first
                needs_stop = node_type not in STATELESS_DEVICES and node_status != "stopped"

                if needs_stop:
                    # Stop node before renaming
                    await gns3.stop_node(current_project_id, node_id)

                    # Wait for node to stop
                    for _ in range(5):
                        await asyncio.sleep(1)
                        nodes = await gns3.get_nodes(current_project_id)
                        current_node = next((n for n in nodes if n["node_id"] == node_id), None)
                        if current_node and current_node["status"] == "stopped":
                            break

                # Now rename the node
                await gns3.update_node(current_project_id, node_id, {"name": requested_name})

                # Restart if we stopped it
                if needs_stop:
                    await gns3.start_node(current_project_id, node_id)
                    node_status = "started"  # Update status in result

                # Update result with corrected name
                result["name"] = requested_name
                result["status"] = node_status
                if "label" in result:
                    result["label"]["text"] = requested_name

        # Convert to NodeSummary for clean output
        node_summary = NodeSummary(
            project_id=current_project_id,
            node_id=result["node_id"],
            name=result["name"],
            node_type=result["node_type"],
            status=result.get("status", "stopped"),
            console_type=result.get("console_type"),
            console=result.get("console"),
        )

        return json.dumps(
            {"message": "Node created successfully", "node": node_summary.model_dump()}, indent=2
        )

    except Exception as e:
        return create_error_response(
            error=f"Failed to create node from template '{template_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify template exists, GNS3 server is accessible, and position coordinates are valid",
            context={
                "template_name": template_name,
                "x": x,
                "y": y,
                "node_name": node_name,
                "exception": str(e),
            },
        )


async def _cleanup_ssh_sessions_for_node(
    ssh_proxy_mapping: Dict[str, str], node_name: str
) -> None:
    """Clean up SSH sessions for a node on all registered proxies (v0.34.0)

    Called automatically when a node is deleted. Attempts to disconnect SSH sessions
    on all proxies (host + lab proxies) and cleans up proxy mappings.

    Args:
        ssh_proxy_mapping: SSH proxy node mapping
        node_name: Name of the deleted node

    Note:
        Errors are logged but not raised - session cleanup should not block node deletion.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Get all registered proxies
            all_proxies = []

            # Always add host proxy
            all_proxies.append({"proxy_id": "host", "url": SSH_PROXY_URL})

            # Try to get lab proxies from registry
            try:
                response = await client.get(f"{SSH_PROXY_URL}/proxy/registry")
                if response.status_code == 200:
                    data = response.json()
                    lab_proxies = data.get("proxies", [])
                    all_proxies.extend(lab_proxies)
            except Exception as e:
                logger.debug(f"Could not fetch lab proxies: {e}")

            # Try to delete SSH session on each proxy
            for proxy in all_proxies:
                proxy_url = proxy.get("url")
                if not proxy_url:
                    continue

                try:
                    response = await client.delete(
                        f"{proxy_url}/ssh/session/{node_name}", timeout=5.0
                    )
                    if response.status_code in (200, 404):
                        logger.debug(
                            f"Cleaned up SSH session for {node_name} on proxy {proxy.get('proxy_id')}"
                        )
                except Exception as e:
                    # Log but don't fail - session cleanup is best-effort
                    logger.debug(
                        f"Could not clean up SSH session for {node_name} on proxy {proxy.get('proxy_id')}: {e}"
                    )

            # Clean up proxy mapping
            ssh_proxy_mapping.pop(node_name, None)

        except Exception as e:
            # Log but don't raise - session cleanup should not block node deletion
            logger.warning(f"SSH session cleanup failed for node {node_name}: {e}")


async def delete_node_impl(
    gns3: "IGns3Client",
    current_project_id: str,
    ssh_proxy_mapping: Dict[str, str],
    node_name: str,
) -> str:
    """Delete a node from the current project

    Also cleans up SSH sessions on all registered proxies.

    Args:
        node_name: Name of the node to delete

    Returns:
        JSON confirmation message
    """
    try:
        nodes = await gns3.get_nodes(current_project_id)
        node = next((n for n in nodes if n["name"] == node_name), None)

        if not node:
            available_nodes = [n["name"] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=current_project_id,
                available_nodes=available_nodes,
            )

        await gns3.delete_node(current_project_id, node["node_id"])

        # Clean up SSH sessions on all registered proxies (v0.34.0)
        await _cleanup_ssh_sessions_for_node(ssh_proxy_mapping, node_name)

        return json.dumps({"message": f"Node '{node_name}' deleted successfully"}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to delete node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify the node exists, stop it if running, and check GNS3 server is accessible",
            context={
                "node_name": node_name,
                "project_id": current_project_id,
                "exception": str(e),
            },
        )


async def get_node_file_impl(
    gns3: "IGns3Client", current_project_id: str, node_name: str, file_path: str
) -> str:
    """Read file from Docker node filesystem

    Args:
        gns3: GNS3 API client
        current_project_id: Current project ID
        node_name: Name of the node
        file_path: Path relative to container root (e.g., 'etc/network/interfaces')

    Returns:
        JSON with file contents
    """
    if not current_project_id:
        return project_not_found_error()

    try:
        nodes = await gns3.get_nodes(current_project_id)
        node = next((n for n in nodes if n["name"] == node_name), None)

        if not node:
            available_nodes = [n["name"] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=current_project_id,
                available_nodes=available_nodes,
            )

        # Validate node type
        if node["node_type"] not in ("docker", "vpcs"):
            return create_error_response(
                error="File operations only supported for Docker and VPCS nodes",
                error_code=ErrorCode.OPERATION_FAILED.value,
                details=f"Node '{node_name}' is type '{node['node_type']}', expected 'docker' or 'vpcs'",
                suggested_action="Only Docker and VPCS nodes support file read/write operations",
                context={
                    "node_name": node_name,
                    "node_type": node["node_type"],
                    "supported_types": ["docker", "vpcs"],
                },
            )

        content = await gns3.get_node_file(current_project_id, node["node_id"], file_path)

        return json.dumps(
            {"node_name": node_name, "file_path": file_path, "content": content}, indent=2
        )

    except Exception as e:
        return create_error_response(
            error=f"Failed to read file '{file_path}' from node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check that the file path is correct and the node is a Docker container",
            context={"node_name": node_name, "file_path": file_path, "exception": str(e)},
        )


async def write_node_file_impl(
    gns3: "IGns3Client",
    current_project_id: str,
    node_name: str,
    file_path: str,
    content: str,
) -> str:
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
    if not current_project_id:
        return project_not_found_error()

    try:
        nodes = await gns3.get_nodes(current_project_id)
        node = next((n for n in nodes if n["name"] == node_name), None)

        if not node:
            available_nodes = [n["name"] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=current_project_id,
                available_nodes=available_nodes,
            )

        # Validate node type
        if node["node_type"] not in ("docker", "vpcs"):
            return create_error_response(
                error="File operations only supported for Docker and VPCS nodes",
                error_code=ErrorCode.OPERATION_FAILED.value,
                details=f"Node '{node_name}' is type '{node['node_type']}', expected 'docker' or 'vpcs'",
                suggested_action="Only Docker and VPCS nodes support file read/write operations",
                context={
                    "node_name": node_name,
                    "node_type": node["node_type"],
                    "supported_types": ["docker", "vpcs"],
                },
            )

        await gns3.write_node_file(current_project_id, node["node_id"], file_path, content)

        return json.dumps(
            {
                "message": f"File '{file_path}' written successfully to node '{node_name}'",
                "node_name": node_name,
                "file_path": file_path,
                "note": "Node restart may be required for changes to take effect",
            },
            indent=2,
        )

    except Exception as e:
        return create_error_response(
            error=f"Failed to write file '{file_path}' to node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check that the file path is valid and the node is a Docker container",
            context={"node_name": node_name, "file_path": file_path, "exception": str(e)},
        )


async def configure_node_network_impl(
    app: "IAppContext", node_name: str, interfaces: list[Dict[str, Any]]
) -> str:
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
        from models import NetworkConfig, NetworkInterfaceDHCP, NetworkInterfaceStatic

        # Validate and parse interfaces
        parsed_interfaces = []
        for iface_dict in interfaces:
            if iface_dict.get("mode") == "static":
                parsed_interfaces.append(NetworkInterfaceStatic(**iface_dict))
            elif iface_dict.get("mode") == "dhcp":
                parsed_interfaces.append(NetworkInterfaceDHCP(**iface_dict))
            else:
                return validation_error(
                    field="interfaces[].mode",
                    message=f"Invalid mode '{iface_dict.get('mode')}', must be 'static' or 'dhcp'",
                )

        config = NetworkConfig(interfaces=parsed_interfaces)

        # Generate interfaces file content
        interfaces_content = config.to_debian_interfaces()

        # Get node
        nodes = await app.gns3.get_nodes(app.current_project_id)
        node = next((n for n in nodes if n["name"] == node_name), None)

        if not node:
            available_nodes = [n["name"] for n in nodes]
            return node_not_found_error(
                node_name=node_name,
                project_id=app.current_project_id,
                available_nodes=available_nodes,
            )

        # Validate node type
        if node["node_type"] not in ("docker", "vpcs"):
            return create_error_response(
                error=f"Network configuration only supported for Docker and VPCS nodes (not {node['node_type']})",
                error_code=ErrorCode.OPERATION_FAILED.value,
                details=f"Node '{node_name}' is type '{node['node_type']}', expected 'docker' or 'vpcs'. QEMU nodes don't support this tool - configure manually via console/SSH.",
                suggested_action="Use console tools or SSH to manually configure network on QEMU/other node types",
                context={
                    "node_name": node_name,
                    "node_type": node["node_type"],
                    "supported_types": ["docker", "vpcs"],
                },
            )

        # Write interfaces file
        await app.gns3.write_node_file(
            app.current_project_id, node["node_id"], "etc/network/interfaces", interfaces_content
        )

        # Restart node to apply configuration
        # Note: Using restart action which stops with retry logic then starts
        await app.gns3.stop_node(app.current_project_id, node["node_id"])

        # Wait for confirmed stop
        for _ in range(10):  # Try up to 10 times
            await asyncio.sleep(1)
            nodes = await app.gns3.get_nodes(app.current_project_id)
            node = next((n for n in nodes if n["node_id"] == node["node_id"]), None)
            if node and node["status"] == "stopped":
                break

        # Start node
        await app.gns3.start_node(app.current_project_id, node["node_id"])

        return json.dumps(
            {
                "message": f"Network configuration applied to node '{node_name}'",
                "node_name": node_name,
                "interfaces": [iface.model_dump() for iface in config.interfaces],
                "status": "Node restarted to apply configuration",
                "note": "Allow 10-15 seconds for node to complete startup and network configuration",
            },
            indent=2,
        )

    except Exception as e:
        return create_error_response(
            error=f"Failed to configure network on node '{node_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check interface configuration parameters and verify node is accessible",
            context={"node_name": node_name, "interfaces": interfaces, "exception": str(e)},
        )
