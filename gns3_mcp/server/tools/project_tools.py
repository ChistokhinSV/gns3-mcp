"""Project management tools for GNS3 MCP Server

Provides tools for listing and opening GNS3 projects.
"""
import json
from typing import TYPE_CHECKING, Optional

from error_utils import create_error_response, project_not_found_error
from models import ErrorCode, ProjectInfo

if TYPE_CHECKING:
    from main import AppContext


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
        return create_error_response(
            error="Failed to list projects",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and accessible",
            context={"exception": str(e)}
        )


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
            return project_not_found_error(project_name)

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
        return create_error_response(
            error=f"Failed to open project '{project_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify project exists in GNS3 and is not corrupted",
            context={"project_name": project_name, "exception": str(e)}
        )


async def create_project_impl(app: "AppContext", name: str, path: Optional[str] = None) -> str:
    """Create a new GNS3 project and auto-open it

    Args:
        name: Project name
        path: Optional project directory path

    Returns:
        JSON with ProjectInfo for created project
    """
    try:
        # Check if project with same name already exists
        projects = await app.gns3.get_projects()
        existing = next((p for p in projects if p['name'] == name), None)

        if existing:
            return create_error_response(
                error=f"Project '{name}' already exists",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details=f"Project with ID {existing['project_id']} already has this name",
                suggested_action="Use open_project() to open existing project, or choose a different name",
                context={"project_name": name, "existing_project_id": existing['project_id']}
            )

        # Create project
        result = await app.gns3.create_project(name, path)

        # Auto-open the project
        await app.gns3.open_project(result['project_id'])
        app.current_project_id = result['project_id']

        # Return ProjectInfo
        project_info = ProjectInfo(
            project_id=result['project_id'],
            name=result['name'],
            status="opened",
            path=result.get('path'),
            filename=result.get('filename')
        )

        return json.dumps(project_info.model_dump(), indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to create project '{name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify GNS3 server is running and you have write permissions",
            context={"project_name": name, "path": path, "exception": str(e)}
        )


async def close_project_impl(app: "AppContext") -> str:
    """Close the currently opened project

    Returns:
        JSON with success message
    """
    try:
        if not app.current_project_id:
            return project_not_found_error()

        # Get project name before closing
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == app.current_project_id), None)
        project_name = project['name'] if project else app.current_project_id

        # Close project
        await app.gns3.close_project(app.current_project_id)

        # Clear current project
        old_project_id = app.current_project_id
        app.current_project_id = None

        return json.dumps({
            "message": "Project closed successfully",
            "project_id": old_project_id,
            "project_name": project_name
        }, indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to close project",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify project is still accessible in GNS3",
            context={"project_id": app.current_project_id, "exception": str(e)}
        )
