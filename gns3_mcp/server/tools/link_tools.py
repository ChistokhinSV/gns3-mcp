"""Link management tools for GNS3 MCP Server

Provides tools for viewing and managing network links (connections) between nodes.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List

from error_utils import create_error_response
from link_validator import LinkValidator
from models import (
    CompletedOperation,
    ConnectOperation,
    ErrorCode,
    FailedOperation,
    LinkEndpoint,
    LinkInfo,
    OperationResult,
    validate_connection_operations,
)

if TYPE_CHECKING:
    from interfaces import IAppContext, IGns3Client

logger = logging.getLogger(__name__)


async def get_links_impl(gns3: "IGns3Client", project_id: str) -> str:
    """List all network links in the current project

    Args:
        gns3: GNS3 API client
        project_id: Current project ID

    Returns:
        JSON array of LinkInfo objects
    """
    try:
        # Get links and nodes directly from API
        links = await gns3.get_links(project_id)
        nodes = await gns3.get_nodes(project_id)

        # Create node ID to name mapping
        node_map = {n["node_id"]: n["name"] for n in nodes}

        # Convert to LinkInfo models
        link_models = []
        warnings = []

        for link in links:
            link_id = link["link_id"]
            link_type = link.get("link_type", "ethernet")
            link_nodes = link.get("nodes", [])

            # Check for corrupted links
            if len(link_nodes) < 2:
                warnings.append(
                    f"Warning: Link {link_id} has only {len(link_nodes)} endpoint(s) - "
                    f"possibly corrupted. Consider deleting with set_connection()"
                )
                continue

            if len(link_nodes) > 2:
                warnings.append(
                    f"Warning: Link {link_id} has {len(link_nodes)} endpoints - "
                    f"unexpected topology (multi-point link?)"
                )

            # Build LinkInfo
            node_a = link_nodes[0]
            node_b = link_nodes[1]

            link_info = LinkInfo(
                link_id=link_id,
                link_type=link_type,
                node_a=LinkEndpoint(
                    node_id=node_a["node_id"],
                    node_name=node_map.get(node_a["node_id"], "Unknown"),
                    adapter_number=node_a.get("adapter_number", 0),
                    port_number=node_a.get("port_number", 0),
                    adapter_type=node_a.get("adapter_type"),
                    port_name=node_a.get("name"),
                ),
                node_b=LinkEndpoint(
                    node_id=node_b["node_id"],
                    node_name=node_map.get(node_b["node_id"], "Unknown"),
                    adapter_number=node_b.get("adapter_number", 0),
                    port_number=node_b.get("port_number", 0),
                    adapter_type=node_b.get("adapter_type"),
                    port_name=node_b.get("name"),
                ),
                capturing=link.get("capturing", False),
                capture_file_name=link.get("capture_file_name"),
                capture_file_path=link.get("capture_file_path"),
                capture_compute_id=link.get("capture_compute_id"),
                suspend=link.get("suspend", False),
            )

            link_models.append(link_info)

        # Build response
        response = {
            "links": [link.model_dump() for link in link_models],
            "warnings": warnings if warnings else None,
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to get links",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and a project is currently open",
            context={"project_id": project_id, "exception": str(e)},
        )


async def set_connection_impl(
    gns3: "IGns3Client", current_project_id: str, connections: List[Dict[str, Any]]
) -> str:
    """Manage network connections (links) in batch with two-phase validation

    Two-phase execution prevents partial topology changes:
    1. VALIDATE ALL operations (check nodes exist, ports free, adapters valid)
    2. EXECUTE ALL operations (only if all valid - atomic)

    Workflow:
        1. Call get_links() to see current topology
        2. Identify link IDs to disconnect (if needed)
        3. Call set_connection() with disconnect + connect operations

    Args:
        connections: List of connection operations:
            Connect: {
                "action": "connect",
                "node_a": "Router1",
                "node_b": "Router2",
                "port_a": 0,
                "port_b": 1,
                "adapter_a": "eth0",  # Port name OR adapter number (int)
                "adapter_b": "GigabitEthernet0/0"  # Port name OR adapter number
            }
            Disconnect: {
                "action": "disconnect",
                "link_id": "abc123"
            }

    Returns:
        JSON with OperationResult (completed and failed operations)
        Includes both port names and adapter/port numbers in confirmation
    """
    try:
        # Validate operation structure with Pydantic
        parsed_ops, validation_error = validate_connection_operations(connections)
        if validation_error:
            return create_error_response(
                error="Invalid operation structure",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details=validation_error,
                suggested_action="Check operation format: connect operations need node_a, node_b, port_a, port_b, adapter_a, adapter_b; disconnect operations need link_id",
                context={"validation_error": validation_error, "operations": connections},
            )

        # Fetch topology data ONCE (not in loop - fixes N+1 issue)
        nodes = await gns3.get_nodes(current_project_id)
        links = await gns3.get_links(current_project_id)

        # PHASE 1: VALIDATE ALL operations (no state changes)
        validator = LinkValidator(nodes, links)

        # Resolve adapter names to numbers and validate
        resolved_ops = []
        for idx, op in enumerate(parsed_ops):
            if isinstance(op, ConnectOperation):
                # Resolve adapter_a
                adapter_a_num, port_a_num, port_a_name, error = (
                    validator.resolve_adapter_identifier(op.node_a, op.adapter_a)
                )
                if error:
                    return create_error_response(
                        error=f"Failed to resolve adapter for {op.node_a}",
                        error_code=ErrorCode.INVALID_ADAPTER.value,
                        details=error,
                        suggested_action="Use valid adapter name (e.g., 'eth0', 'GigabitEthernet0/0') or adapter number (0, 1, 2, ...)",
                        context={
                            "node_name": op.node_a,
                            "adapter": op.adapter_a,
                            "operation_index": idx,
                        },
                    )

                # Resolve adapter_b
                adapter_b_num, port_b_num, port_b_name, error = (
                    validator.resolve_adapter_identifier(op.node_b, op.adapter_b)
                )
                if error:
                    return create_error_response(
                        error=f"Failed to resolve adapter for {op.node_b}",
                        error_code=ErrorCode.INVALID_ADAPTER.value,
                        details=error,
                        suggested_action="Use valid adapter name (e.g., 'eth0', 'GigabitEthernet0/0') or adapter number (0, 1, 2, ...)",
                        context={
                            "node_name": op.node_b,
                            "adapter": op.adapter_b,
                            "operation_index": idx,
                        },
                    )

                # Store resolved values
                resolved_ops.append(
                    {
                        "op": op,
                        "adapter_a_num": adapter_a_num,
                        "port_a_num": port_a_num,
                        "port_a_name": port_a_name,
                        "adapter_b_num": adapter_b_num,
                        "port_b_num": port_b_num,
                        "port_b_name": port_b_name,
                    }
                )

                # Validate with resolved numbers
                validation_error = validator.validate_connect(
                    op.node_a, op.node_b, op.port_a, op.port_b, adapter_a_num, adapter_b_num
                )
            else:  # DisconnectOperation
                resolved_ops.append({"op": op})
                validation_error = validator.validate_disconnect(op.link_id)

            if validation_error:
                # Determine error code based on validation message
                if "already connected" in validation_error or "in use" in validation_error:
                    error_code = ErrorCode.PORT_IN_USE.value
                elif "not found" in validation_error:
                    if "Node" in validation_error:
                        error_code = ErrorCode.NODE_NOT_FOUND.value
                    elif "Link" in validation_error:
                        error_code = ErrorCode.LINK_NOT_FOUND.value
                    else:
                        error_code = ErrorCode.INVALID_PARAMETER.value
                else:
                    error_code = ErrorCode.INVALID_PARAMETER.value

                return create_error_response(
                    error=f"Validation failed at operation {idx}",
                    error_code=error_code,
                    details=validation_error,
                    suggested_action="Check get_links() to see current topology and verify node names, ports, and adapters",
                    context={"operation_index": idx, "operation": op.model_dump()},
                )

        logger.info(f"All {len(parsed_ops)} operations validated successfully")

        # PHASE 2: EXECUTE ALL operations (all validated - safe to proceed)
        completed = []
        failed = None
        node_map = {n["name"]: n for n in nodes}

        for idx, resolved in enumerate(resolved_ops):
            op = resolved["op"]
            try:
                if isinstance(op, ConnectOperation):
                    # Build link spec with resolved adapter numbers
                    node_a = node_map[op.node_a]
                    node_b = node_map[op.node_b]

                    link_spec = {
                        "nodes": [
                            {
                                "node_id": node_a["node_id"],
                                "adapter_number": resolved["adapter_a_num"],
                                "port_number": op.port_a,
                            },
                            {
                                "node_id": node_b["node_id"],
                                "adapter_number": resolved["adapter_b_num"],
                                "port_number": op.port_b,
                            },
                        ]
                    }

                    result = await gns3.create_link(current_project_id, link_spec)

                    completed.append(
                        CompletedOperation(
                            index=idx,
                            action="connect",
                            link_id=result.get("link_id"),
                            node_a=op.node_a,
                            node_b=op.node_b,
                            port_a=op.port_a,
                            port_b=op.port_b,
                            adapter_a=resolved["adapter_a_num"],
                            adapter_b=resolved["adapter_b_num"],
                            port_a_name=resolved["port_a_name"],
                            port_b_name=resolved["port_b_name"],
                        )
                    )

                    logger.info(
                        f"Connected {op.node_a} {resolved['port_a_name']} (adapter {resolved['adapter_a_num']}) <-> "
                        f"{op.node_b} {resolved['port_b_name']} (adapter {resolved['adapter_b_num']})"
                    )

                else:  # Disconnect
                    await gns3.delete_link(current_project_id, op.link_id)

                    completed.append(
                        CompletedOperation(index=idx, action="disconnect", link_id=op.link_id)
                    )

                    logger.info(f"Disconnected link {op.link_id}")

            except Exception as e:
                # Execution failed (should be rare after validation)
                failed = FailedOperation(
                    index=idx, action=op.action, operation=op.model_dump(), reason=str(e)
                )
                logger.error(f"Operation {idx} failed during execution: {str(e)}")
                break

        # Build result
        result = OperationResult(completed=completed, failed=failed)
        return json.dumps(result.model_dump(), indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to manage connections",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check GNS3 server is accessible, verify operation format, and review GNS3 server logs",
            context={"operations": connections, "exception": str(e)},
        )
