"""Drawing management tools for GNS3 MCP Server

Provides tools for creating and managing drawing objects (shapes, text, lines).
"""
import json
from typing import TYPE_CHECKING, Optional

from models import DrawingInfo, ErrorResponse, ErrorCode
from error_utils import create_error_response, drawing_not_found_error
from export_tools import (
    create_rectangle_svg,
    create_ellipse_svg,
    create_line_svg,
    create_text_svg
)

if TYPE_CHECKING:
    from main import AppContext


async def list_drawings_impl(app: "AppContext") -> str:
    """List all drawing objects in the current project

    Returns:
        JSON array of DrawingInfo objects
    """
    try:
        drawings = await app.gns3.get_drawings(app.current_project_id)

        drawing_models = [
            DrawingInfo(
                drawing_id=d['drawing_id'],
                project_id=d['project_id'],
                x=d['x'],
                y=d['y'],
                z=d.get('z', 0),
                rotation=d.get('rotation', 0),
                svg=d['svg'],
                locked=d.get('locked', False)
            )
            for d in drawings
        ]

        return json.dumps([d.model_dump() for d in drawing_models], indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to list drawings",
            error_code=ErrorCode.GNS3_API_ERROR.value,
            details=str(e),
            suggested_action="Check that GNS3 server is running and a project is currently open",
            context={"project_id": app.current_project_id, "exception": str(e)}
        )


async def create_drawing_impl(app: "AppContext",
                              drawing_type: str,
                              x: int,
                              y: int,
                              z: int = 0,
                              # Rectangle/Ellipse parameters
                              width: Optional[int] = None,
                              height: Optional[int] = None,
                              rx: Optional[int] = None,
                              ry: Optional[int] = None,
                              fill_color: str = "#ffffff",
                              border_color: str = "#000000",
                              border_width: int = 2,
                              # Line parameters
                              x2: Optional[int] = None,
                              y2: Optional[int] = None,
                              # Text parameters
                              text: Optional[str] = None,
                              font_size: int = 10,
                              font_weight: str = "normal",
                              font_family: str = "TypeWriter",
                              color: str = "#000000") -> str:
    """Create a drawing object (rectangle, ellipse, line, or text)

    Args:
        drawing_type: Type of drawing - "rectangle", "ellipse", "line", or "text"
        x: X coordinate (start point for line, top-left for others)
        y: Y coordinate (start point for line, top-left for others)
        z: Z-order/layer (default: 0 for shapes, 1 for text)

        Rectangle parameters (drawing_type="rectangle"):
            width: Rectangle width (required)
            height: Rectangle height (required)
            fill_color: Fill color (hex or name, default: white)
            border_color: Border color (default: black)
            border_width: Border width in pixels (default: 2)

        Ellipse parameters (drawing_type="ellipse"):
            rx: Horizontal radius (required)
            ry: Vertical radius (required, use same as rx for circle)
            fill_color: Fill color (hex or name, default: white)
            border_color: Border color (default: black)
            border_width: Border width in pixels (default: 2)
            Note: Ellipse center will be at (x + rx, y + ry)

        Line parameters (drawing_type="line"):
            x2: X offset from start point (required, can be negative)
            y2: Y offset from start point (required, can be negative)
            color: Line color (hex or name, default: black)
            border_width: Line width in pixels (default: 2)
            Note: Line goes from (x, y) to (x+x2, y+y2)

        Text parameters (drawing_type="text"):
            text: Text content (required)
            font_size: Font size in points (default: 10)
            font_weight: Font weight - "normal" or "bold" (default: normal)
            font_family: Font family (default: "TypeWriter")
            color: Text color (hex or name, default: black)

    Returns:
        JSON with created drawing info

    Examples:
        # Create rectangle
        create_drawing("rectangle", x=100, y=100, width=200, height=150,
                      fill_color="#ff0000", z=0)

        # Create circle
        create_drawing("ellipse", x=100, y=100, rx=50, ry=50,
                      fill_color="#00ff00", z=0)

        # Create line from (100,100) to (300,200)
        create_drawing("line", x=100, y=100, x2=200, y2=100,
                      color="#0000ff", border_width=3, z=0)

        # Create text label
        create_drawing("text", x=100, y=100, text="Router1",
                      font_size=12, font_weight="bold", z=1)
    """
    try:
        drawing_type = drawing_type.lower()

        # Generate appropriate SVG based on type
        if drawing_type == "rectangle":
            if width is None or height is None:
                return create_error_response(
                    error="Missing required parameters for rectangle",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Rectangle requires 'width' and 'height' parameters",
                    suggested_action="Provide width and height parameters",
                    context={"drawing_type": drawing_type, "width": width, "height": height}
                )

            svg = create_rectangle_svg(width, height, fill_color, border_color, border_width)
            message = "Rectangle created successfully"

        elif drawing_type == "ellipse":
            if rx is None or ry is None:
                return create_error_response(
                    error="Missing required parameters for ellipse",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Ellipse requires 'rx' and 'ry' parameters",
                    suggested_action="Provide rx and ry parameters (horizontal and vertical radii)",
                    context={"drawing_type": drawing_type, "rx": rx, "ry": ry}
                )

            svg = create_ellipse_svg(rx, ry, fill_color, border_color, border_width)
            message = "Ellipse created successfully"

        elif drawing_type == "line":
            if x2 is None or y2 is None:
                return create_error_response(
                    error="Missing required parameters for line",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Line requires 'x2' and 'y2' parameters (offset from start point)",
                    suggested_action="Provide x2 and y2 parameters to define line endpoint",
                    context={"drawing_type": drawing_type, "x2": x2, "y2": y2}
                )

            svg = create_line_svg(x2, y2, color, border_width)
            message = "Line created successfully"

        elif drawing_type == "text":
            if text is None:
                return create_error_response(
                    error="Missing required parameter for text",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Text drawing requires 'text' parameter",
                    suggested_action="Provide text parameter with the text content to display",
                    context={"drawing_type": drawing_type}
                )

            svg = create_text_svg(text, font_size, font_weight, font_family, color)
            message = "Text created successfully"

        else:
            from error_utils import validation_error
            return validation_error(
                message=f"Invalid drawing type '{drawing_type}'",
                parameter="drawing_type",
                value=drawing_type,
                valid_values=["rectangle", "ellipse", "line", "text"]
            )

        # Create drawing in GNS3
        drawing_data = {
            "x": x,
            "y": y,
            "z": z,
            "svg": svg,
            "rotation": 0
        }

        result = await app.gns3.create_drawing(app.current_project_id, drawing_data)

        return json.dumps({"message": message, "drawing": result}, indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to create drawing",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check drawing parameters are valid and GNS3 server is accessible",
            context={"drawing_type": drawing_type, "x": x, "y": y, "z": z, "exception": str(e)}
        )


async def update_drawing_impl(app: "AppContext",
                              drawing_id: str,
                              x: Optional[int] = None,
                              y: Optional[int] = None,
                              z: Optional[int] = None,
                              rotation: Optional[int] = None,
                              svg: Optional[str] = None,
                              locked: Optional[bool] = None) -> str:
    """Update properties of an existing drawing object

    Args:
        drawing_id: ID of the drawing to update
        x: New X coordinate (optional)
        y: New Y coordinate (optional)
        z: New Z-order/layer (optional)
        rotation: New rotation angle in degrees (optional)
        svg: New SVG content (optional, for changing appearance)
        locked: Lock/unlock drawing (optional)

    Returns:
        JSON with updated drawing info

    Example:
        # Move drawing to new position
        update_drawing("draw-123", x=200, y=150)

        # Rotate drawing 45 degrees
        update_drawing("draw-123", rotation=45)

        # Lock drawing position
        update_drawing("draw-123", locked=True)
    """
    try:
        # Build update payload with only provided parameters
        update_data = {}
        if x is not None:
            update_data["x"] = x
        if y is not None:
            update_data["y"] = y
        if z is not None:
            update_data["z"] = z
        if rotation is not None:
            update_data["rotation"] = rotation
        if svg is not None:
            update_data["svg"] = svg
        if locked is not None:
            update_data["locked"] = locked

        if not update_data:
            return create_error_response(
                error="No update parameters provided",
                error_code=ErrorCode.MISSING_PARAMETER.value,
                details="Provide at least one parameter to update (x, y, z, rotation, svg, locked)",
                suggested_action="Specify at least one parameter: x, y, z, rotation, svg, or locked",
                context={"drawing_id": drawing_id}
            )

        # Update drawing in GNS3
        result = await app.gns3.update_drawing(app.current_project_id, drawing_id, update_data)

        return json.dumps({"message": "Drawing updated successfully", "drawing": result}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to update drawing '{drawing_id}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify drawing ID exists and update parameters are valid",
            context={"drawing_id": drawing_id, "update_data": update_data, "exception": str(e)}
        )


async def delete_drawing_impl(app: "AppContext", drawing_id: str) -> str:
    """Delete a drawing object from the current project

    Args:
        drawing_id: ID of the drawing to delete

    Returns:
        JSON confirmation message
    """
    try:
        await app.gns3.delete_drawing(app.current_project_id, drawing_id)
        return json.dumps({"message": f"Drawing {drawing_id} deleted successfully"}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to delete drawing '{drawing_id}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify drawing ID exists using list_drawings() or resource gns3://projects/{id}/drawings/",
            context={"drawing_id": drawing_id, "project_id": app.current_project_id, "exception": str(e)}
        )
