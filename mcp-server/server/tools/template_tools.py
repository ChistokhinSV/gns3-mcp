"""Template management tools for GNS3 MCP Server

Provides tools for listing available GNS3 device templates.
"""
import json
from typing import TYPE_CHECKING

from models import TemplateInfo, ErrorResponse, ErrorCode
from error_utils import create_error_response

if TYPE_CHECKING:
    from main import AppContext


async def list_templates_impl(app: "AppContext") -> str:
    """List all available GNS3 templates

    Returns:
        JSON array of TemplateInfo objects
    """
    try:
        templates = await app.gns3.get_templates()

        template_models = [
            TemplateInfo(
                template_id=t['template_id'],
                name=t['name'],
                category=t.get('category', 'default'),
                node_type=t.get('template_type'),
                compute_id=t.get('compute_id') or 'local',
                builtin=t.get('builtin', False),
                symbol=t.get('symbol')
            )
            for t in templates
        ]

        return json.dumps([t.model_dump() for t in template_models], indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to list templates",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and accessible",
            context={"exception": str(e)}
        )
