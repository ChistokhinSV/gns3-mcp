"""Snapshot management tools for GNS3 MCP Server

Provides tools for creating and restoring project snapshots.
"""
import json
from typing import TYPE_CHECKING, List

from models import SnapshotInfo, ErrorResponse, ErrorCode
from error_utils import create_error_response, project_not_found_error, snapshot_not_found_error

if TYPE_CHECKING:
    from main import Context, AppContext


async def create_snapshot_impl(app: "AppContext", name: str, description: str = "") -> str:
    """Create snapshot of current project state

    Uses validation-then-execute pattern:
    1. Validate project is open
    2. Check for duplicate snapshot name
    3. Warn if nodes are running (non-blocking)
    4. Execute snapshot creation

    Args:
        app: Application context
        name: Snapshot name
        description: Optional snapshot description

    Returns:
        JSON with SnapshotInfo for created snapshot
    """
    try:
        # 1. Validate project is open
        if not app.current_project_id:
            return project_not_found_error()

        # 2. Check for duplicate snapshot name
        snapshots = await app.gns3.get_snapshots(app.current_project_id)
        if any(s.get('name') == name for s in snapshots):
            return create_error_response(
                error=f"Snapshot name '{name}' already exists",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details=f"A snapshot named '{name}' already exists in this project",
                suggested_action="Use a different snapshot name or delete the existing snapshot first",
                context={"snapshot_name": name, "project_id": app.current_project_id}
            )

        # 3. Warn if nodes are running (non-blocking)
        warnings: List[str] = []
        nodes = await app.gns3.get_nodes(app.current_project_id)
        running_nodes = [n['name'] for n in nodes if n.get('status') == 'started']
        if running_nodes:
            warnings.append(
                f"Warning: Snapshot created with {len(running_nodes)} running node(s): {', '.join(running_nodes)}. "
                f"For consistent snapshots, consider stopping all nodes first."
            )

        # 4. Execute snapshot creation
        result = await app.gns3.create_snapshot(app.current_project_id, name, description)

        # Convert to SnapshotInfo
        snapshot_info = SnapshotInfo(
            snapshot_id=result['snapshot_id'],
            name=result['name'],
            created_at=result.get('created_at', ''),
            project_id=app.current_project_id
        )

        response = {
            "message": "Snapshot created successfully",
            "snapshot": snapshot_info.model_dump()
        }

        if warnings:
            response["warnings"] = warnings

        return json.dumps(response, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to create snapshot '{name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify project is accessible, you have write permissions, and GNS3 server has disk space",
            context={"snapshot_name": name, "project_id": app.current_project_id, "exception": str(e)}
        )


async def restore_snapshot_impl(app: "AppContext", snapshot_name: str) -> str:
    """Restore project to a previous snapshot state

    Implementation steps:
    1. Validate project is open
    2. Find snapshot by name
    3. Stop all running nodes
    4. Disconnect all console sessions
    5. Execute snapshot restore

    Args:
        app: Application context
        snapshot_name: Name of the snapshot to restore

    Returns:
        JSON with success message and restore details
    """
    try:
        # 1. Validate project is open
        if not app.current_project_id:
            return project_not_found_error()

        # 2. Find snapshot by name
        snapshots = await app.gns3.get_snapshots(app.current_project_id)
        snapshot = next((s for s in snapshots if s.get('name') == snapshot_name), None)

        if not snapshot:
            available = [s.get('name') for s in snapshots]
            return snapshot_not_found_error(
                snapshot_name=snapshot_name,
                project_id=app.current_project_id,
                available_snapshots=available
            )

        snapshot_id = snapshot['snapshot_id']

        # 3. Stop all running nodes
        nodes = await app.gns3.get_nodes(app.current_project_id)
        running_nodes = [n for n in nodes if n.get('status') == 'started']
        stopped_nodes: List[str] = []

        for node in running_nodes:
            try:
                await app.gns3.stop_node(app.current_project_id, node['node_id'])
                stopped_nodes.append(node['name'])
            except Exception as e:
                # Log error but continue with other nodes
                pass

        # 4. Disconnect all console sessions
        disconnected_sessions: List[str] = []
        for node in nodes:
            node_name = node['name']
            if app.console.has_session(node_name):
                await app.console.disconnect(node_name)
                disconnected_sessions.append(node_name)

        # 5. Execute snapshot restore
        result = await app.gns3.restore_snapshot(app.current_project_id, snapshot_id)

        response = {
            "message": "Snapshot restored successfully",
            "snapshot_name": snapshot_name,
            "snapshot_id": snapshot_id,
            "stopped_nodes": stopped_nodes,
            "disconnected_sessions": disconnected_sessions
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to restore snapshot '{snapshot_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify snapshot exists, project is accessible, and all nodes are stopped",
            context={"snapshot_name": snapshot_name, "project_id": app.current_project_id, "exception": str(e)}
        )
