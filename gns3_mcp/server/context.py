"""Application Context Helpers

Utilities for working with global application context and validation.

v0.49.0: Extracted from main.py for better modularity (GM-45)
"""

import json
import logging
from typing import TYPE_CHECKING

from models import ErrorResponse

if TYPE_CHECKING:
    from interfaces import IAppContext

logger = logging.getLogger(__name__)

# Global app context for static resources (set during lifespan)
_app: "IAppContext | None" = None


def get_app() -> "IAppContext":
    """Get global app context (for resources that don't have Context)

    Raises:
        RuntimeError: If application not initialized

    Returns:
        Application context
    """
    if _app is None:
        raise RuntimeError("Application not initialized")
    return _app


def set_app(app: "IAppContext") -> None:
    """Set global app context

    Called during application startup.

    Args:
        app: Application context to set
    """
    global _app
    _app = app


def clear_app() -> None:
    """Clear global app context

    Called during application shutdown.
    """
    global _app
    _app = None


async def validate_current_project(app: "IAppContext") -> str | None:
    """Validate that current project is still open, with auto-connect to opened projects

    If no project is connected but one is opened in GNS3, automatically connects to it.
    This provides seamless UX when projects are opened via GNS3 GUI.

    Args:
        app: Application context

    Returns:
        Error message (JSON string) if invalid, None if valid
    """
    try:
        # Get project list directly from API
        projects = await app.gns3.get_projects()

        # If no project connected, try to auto-connect to opened project
        if not app.current_project_id:
            opened = [p for p in projects if p.get("status") == "opened"]

            if not opened:
                return json.dumps(
                    ErrorResponse(
                        error="No project opened in GNS3",
                        details="No projects are currently opened. Open a project in GNS3 or use open_project()",
                        suggested_action="Open a project in GNS3 GUI, or call list_projects() then open_project(project_name)",
                    ).model_dump(),
                    indent=2,
                )

            # Auto-connect to the first opened project
            app.current_project_id = opened[0]["project_id"]
            logger.info(
                f"Auto-connected to opened project: {opened[0]['name']} ({opened[0]['project_id']})"
            )

            if len(opened) > 1:
                logger.warning(
                    f"Multiple projects opened ({len(opened)}), connected to: {opened[0]['name']}"
                )

            return None  # Successfully auto-connected

        # Validate that connected project still exists and is opened
        project = next((p for p in projects if p["project_id"] == app.current_project_id), None)

        if not project:
            app.current_project_id = None
            return json.dumps(
                ErrorResponse(
                    error="Project no longer exists",
                    details=f"Project ID {app.current_project_id} not found. Use list_projects() and open_project()",
                    suggested_action="Call list_projects() to see current projects, then open_project(project_name)",
                ).model_dump(),
                indent=2,
            )

        if project["status"] != "opened":
            app.current_project_id = None
            return json.dumps(
                ErrorResponse(
                    error=f"Project is {project['status']}",
                    details=f"Project '{project['name']}' is not open. Use open_project() to reopen",
                    suggested_action=f"Call open_project('{project['name']}') to reopen this project",
                ).model_dump(),
                indent=2,
            )

        return None

    except Exception as e:
        return json.dumps(
            ErrorResponse(
                error="Failed to validate project",
                details=str(e),
                suggested_action="Check GNS3 server connection and project state",
            ).model_dump(),
            indent=2,
        )
