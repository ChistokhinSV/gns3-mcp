"""Drawing management tools for GNS3 MCP Server

Provides tools for creating and managing drawing objects (shapes, text, lines).
"""
import json
from typing import TYPE_CHECKING, Optional

from models import DrawingInfo, ErrorResponse
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
        return json.dumps(ErrorResponse(
            error="Failed to list drawings",
            details=str(e)
        ).model_dump(), indent=2)


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
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Rectangle requires 'width' and 'height' parameters"
                ).model_dump(), indent=2)

            svg = create_rectangle_svg(width, height, fill_color, border_color, border_width)
            message = "Rectangle created successfully"

        elif drawing_type == "ellipse":
            if rx is None or ry is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Ellipse requires 'rx' and 'ry' parameters"
                ).model_dump(), indent=2)

            svg = create_ellipse_svg(rx, ry, fill_color, border_color, border_width)
            message = "Ellipse created successfully"

        elif drawing_type == "line":
            if x2 is None or y2 is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Line requires 'x2' and 'y2' parameters (offset from start point)"
                ).model_dump(), indent=2)

            svg = create_line_svg(x2, y2, color, border_width)
            message = "Line created successfully"

        elif drawing_type == "text":
            if text is None:
                return json.dumps(ErrorResponse(
                    error="Missing required parameters",
                    details="Text drawing requires 'text' parameter"
                ).model_dump(), indent=2)

            svg = create_text_svg(text, font_size, font_weight, font_family, color)
            message = "Text created successfully"

        else:
            return json.dumps(ErrorResponse(
                error="Invalid drawing type",
                details=f"drawing_type must be 'rectangle', 'ellipse', 'line', or 'text', got '{drawing_type}'"
            ).model_dump(), indent=2)

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
        return json.dumps(ErrorResponse(
            error="Failed to create drawing",
            details=str(e)
        ).model_dump(), indent=2)


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
        return json.dumps(ErrorResponse(
            error="Failed to delete drawing",
            details=str(e)
        ).model_dump(), indent=2)
