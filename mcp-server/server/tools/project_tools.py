"""Project management tools for GNS3 MCP Server

Provides tools for listing and opening GNS3 projects.
"""
import json
from typing import TYPE_CHECKING

from models import ProjectInfo, ErrorResponse

if TYPE_CHECKING:
    from main import Context, AppContext


async def list_projects_impl(app: "AppContext") -> str:
    """List all GNS3 projects with their status

    Returns:
        JSON array of ProjectInfo objects
    """
    try:
        # Get projects directly from API
        projects = await app.gns3.get_projects()

        # Convert to ProjectInfo models
        project_models = [
            ProjectInfo(
                project_id=p['project_id'],
                name=p['name'],
                status=p['status'],
                path=p.get('path'),
                filename=p.get('filename'),
                auto_start=p.get('auto_start', False),
                auto_close=p.get('auto_close', True),
                auto_open=p.get('auto_open', False)
            )
            for p in projects
        ]

        return json.dumps([p.model_dump() for p in project_models], indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to list projects",
            details=str(e)
        ).model_dump(), indent=2)


async def open_project_impl(app: "AppContext", project_name: str) -> str:
    """Open a GNS3 project by name

    Args:
        project_name: Name of the project to open

    Returns:
        JSON with ProjectInfo for opened project
    """
    try:
        # Find project by name
        projects = await app.gns3.get_projects()

        project = next((p for p in projects if p['name'] == project_name), None)

        if not project:
            return json.dumps(ErrorResponse(
                error="Project not found",
                details=f"No project named '{project_name}' found. Use list_projects() to see available projects.",
                suggested_action="Call list_projects() to see exact project names (case-sensitive)"
            ).model_dump(), indent=2)

        # Open it
        result = await app.gns3.open_project(project['project_id'])
        app.current_project_id = project['project_id']

        # Return ProjectInfo
        project_info = ProjectInfo(
            project_id=result['project_id'],
            name=result['name'],
            status=result['status'],
            path=result.get('path'),
            filename=result.get('filename')
        )

        return json.dumps(project_info.model_dump(), indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to open project",
            details=str(e),
            suggested_action="Verify project exists in GNS3 and is not corrupted"
        ).model_dump(), indent=2)
