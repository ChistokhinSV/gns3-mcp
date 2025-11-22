"""Project management tools for GNS3 MCP Server

Provides tools for listing and opening GNS3 projects.
"""

import json
from typing import TYPE_CHECKING

from error_utils import create_error_response, project_not_found_error
from models import ErrorCode, ProjectInfo

if TYPE_CHECKING:
    from interfaces import IAppContext, IGns3Client


async def list_projects_impl(gns3: "IGns3Client", format: str = "table") -> str:
    """List all GNS3 projects with their status

    Args:
        gns3: GNS3 API client
        format: Output format ('table' or 'json')

    Returns:
        JSON array of ProjectInfo objects or formatted table
    """
    try:
        # Get projects directly from API
        projects = await gns3.get_projects()

        # Convert to ProjectInfo models
        project_models = [
            ProjectInfo(
                project_id=p["project_id"],
                name=p["name"],
                status=p["status"],
                path=p.get("path"),
                filename=p.get("filename"),
                auto_start=p.get("auto_start", False),
                auto_close=p.get("auto_close", True),
                auto_open=p.get("auto_open", False),
            )
            for p in projects
        ]

        if format == "json":
            return json.dumps([p.model_dump() for p in project_models], indent=2)
        else:
            # Table format
            from tabulate import tabulate

            headers = ["Name", "Status", "Project ID"]
            rows = [[p.name, p.status, p.project_id] for p in project_models]
            table = tabulate(rows, headers=headers, tablefmt="simple")
            return table

    except Exception as e:
        return create_error_response(
            error="Failed to list projects",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and accessible",
            context={"exception": str(e)},
        )


async def open_project_impl(gns3: "IGns3Client", project_name: str) -> tuple[str, str]:
    """Open a GNS3 project by name

    Args:
        gns3: GNS3 API client
        project_name: Name of the project to open

    Returns:
        Tuple of (JSON with ProjectInfo for opened project, new project_id)
    """
    try:
        # Find project by name
        projects = await gns3.get_projects()

        project = next((p for p in projects if p["name"] == project_name), None)

        if not project:
            error_response = project_not_found_error(project_name)
            # Return error response with empty project_id since we failed
            return (error_response, "")

        # Open it
        result = await gns3.open_project(project["project_id"])
        new_project_id = project["project_id"]

        # Return ProjectInfo
        project_info = ProjectInfo(
            project_id=result["project_id"],
            name=result["name"],
            status=result["status"],
            path=result.get("path"),
            filename=result.get("filename"),
        )

        return (json.dumps(project_info.model_dump(), indent=2), new_project_id)

    except Exception as e:
        error_response = create_error_response(
            error=f"Failed to open project '{project_name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify project exists in GNS3 and is not corrupted",
            context={"project_name": project_name, "exception": str(e)},
        )
        return (error_response, "")


async def create_project_impl(gns3: "IGns3Client", name: str, path: str | None = None) -> tuple[str, str]:
    """Create a new GNS3 project and auto-open it

    Args:
        gns3: GNS3 API client
        name: Project name
        path: Optional project directory path

    Returns:
        Tuple of (JSON with ProjectInfo for created project, new project_id)
    """
    try:
        # Check if project with same name already exists
        projects = await gns3.get_projects()
        existing = next((p for p in projects if p["name"] == name), None)

        if existing:
            error_response = create_error_response(
                error=f"Project '{name}' already exists",
                error_code=ErrorCode.INVALID_PARAMETER.value,
                details=f"Project with ID {existing['project_id']} already has this name",
                suggested_action="Use open_project() to open existing project, or choose a different name",
                context={"project_name": name, "existing_project_id": existing["project_id"]},
            )
            return (error_response, "")

        # Create project
        result = await gns3.create_project(name, path)

        # Auto-open the project
        await gns3.open_project(result["project_id"])
        new_project_id = result["project_id"]

        # Return ProjectInfo
        project_info = ProjectInfo(
            project_id=result["project_id"],
            name=result["name"],
            status="opened",
            path=result.get("path"),
            filename=result.get("filename"),
        )

        return (json.dumps(project_info.model_dump(), indent=2), new_project_id)

    except Exception as e:
        error_response = create_error_response(
            error=f"Failed to create project '{name}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify GNS3 server is running and you have write permissions",
            context={"project_name": name, "path": path, "exception": str(e)},
        )
        return (error_response, "")


async def close_project_impl(gns3: "IGns3Client", current_project_id: str | None) -> tuple[str, None]:
    """Close the currently opened project

    Args:
        gns3: GNS3 API client
        current_project_id: Current project ID to close

    Returns:
        Tuple of (JSON with success message, None to clear project_id)
    """
    try:
        if not current_project_id:
            error_response = project_not_found_error()
            return (error_response, None)

        # Get project name before closing
        projects = await gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == current_project_id), None)
        project_name = project["name"] if project else current_project_id

        # Close project
        await gns3.close_project(current_project_id)

        # Return success with None to signal clearing current_project_id
        result = json.dumps(
            {
                "message": "Project closed successfully",
                "project_id": current_project_id,
                "project_name": project_name,
            },
            indent=2,
        )
        return (result, None)

    except Exception as e:
        error_response = create_error_response(
            error="Failed to close project",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify project is still accessible in GNS3",
            context={"project_id": current_project_id, "exception": str(e)},
        )
        return (error_response, None)
