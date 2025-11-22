"""Drawing management tools for GNS3 MCP Server

Provides tools for creating and managing drawing objects (shapes, text, lines).
"""

import json
from typing import TYPE_CHECKING

from error_utils import create_error_response, validation_error
from export_tools import create_ellipse_svg, create_line_svg, create_rectangle_svg, create_text_svg
from models import DrawingInfo, ErrorCode

if TYPE_CHECKING:
    from interfaces import IAppContext


async def list_drawings_impl(app: "IAppContext") -> str:
    """List all drawing objects in the current project

    Returns:
        JSON array of DrawingInfo objects
    """
    try:
        drawings = await app.gns3.get_drawings(app.current_project_id)

        drawing_models = [
            DrawingInfo(
                drawing_id=d["drawing_id"],
                project_id=d["project_id"],
                x=d["x"],
                y=d["y"],
                z=d.get("z", 0),
                rotation=d.get("rotation", 0),
                svg=d["svg"],
                locked=d.get("locked", False),
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
            context={"project_id": app.current_project_id, "exception": str(e)},
        )


async def create_drawing_impl(
    gns3: "IGns3Client",
    current_project_id: str,
    drawing_type: str,
    x: int,
    y: int,
    z: int = 0,
    # Rectangle/Ellipse parameters
    width: int | None = None,
    height: int | None = None,
    rx: int | None = None,
    ry: int | None = None,
    fill_color: str = "#ffffff",
    border_color: str = "#000000",
    border_width: int = 2,
    # Line parameters
    x2: int | None = None,
    y2: int | None = None,
    # Text parameters
    text: str | None = None,
    font_size: int = 10,
    font_weight: str = "normal",
    font_family: str = "TypeWriter",
    color: str = "#000000",
) -> str:
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
                    context={"drawing_type": drawing_type, "width": width, "height": height},
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
                    context={"drawing_type": drawing_type, "rx": rx, "ry": ry},
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
                    context={"drawing_type": drawing_type, "x2": x2, "y2": y2},
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
                    context={"drawing_type": drawing_type},
                )

            svg = create_text_svg(text, font_size, font_weight, font_family, color)
            message = "Text created successfully"

        else:
            from error_utils import validation_error

            return validation_error(
                message=f"Invalid drawing type '{drawing_type}'",
                parameter="drawing_type",
                value=drawing_type,
                valid_values=["rectangle", "ellipse", "line", "text"],
            )

        # Create drawing in GNS3
        drawing_data = {"x": x, "y": y, "z": z, "svg": svg, "rotation": 0}

        result = await gns3.create_drawing(current_project_id, drawing_data)

        return json.dumps({"message": message, "drawing": result}, indent=2)

    except Exception as e:
        return create_error_response(
            error="Failed to create drawing",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Check drawing parameters are valid and GNS3 server is accessible",
            context={"drawing_type": drawing_type, "x": x, "y": y, "z": z, "exception": str(e)},
        )


async def update_drawing_impl(
    gns3: "IGns3Client",
    current_project_id: str,
    drawing_id: str,
    x: int | None = None,
    y: int | None = None,
    z: int | None = None,
    rotation: int | None = None,
    svg: str | None = None,
    locked: bool | None = None,
) -> str:
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
                context={"drawing_id": drawing_id},
            )

        # Update drawing in GNS3
        result = await gns3.update_drawing(current_project_id, drawing_id, update_data)

        return json.dumps({"message": "Drawing updated successfully", "drawing": result}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to update drawing '{drawing_id}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify drawing ID exists and update parameters are valid",
            context={"drawing_id": drawing_id, "update_data": update_data, "exception": str(e)},
        )


async def delete_drawing_impl(
    gns3: "IGns3Client", current_project_id: str, drawing_id: str
) -> str:
    """Delete a drawing object from the current project

    Args:
        drawing_id: ID of the drawing to delete

    Returns:
        JSON confirmation message
    """
    try:
        await gns3.delete_drawing(current_project_id, drawing_id)
        return json.dumps({"message": f"Drawing {drawing_id} deleted successfully"}, indent=2)

    except Exception as e:
        return create_error_response(
            error=f"Failed to delete drawing '{drawing_id}'",
            error_code=ErrorCode.OPERATION_FAILED.value,
            details=str(e),
            suggested_action="Verify drawing ID exists using list_drawings() or resource projects://{id}/drawings/",
            context={
                "drawing_id": drawing_id,
                "project_id": current_project_id,
                "exception": str(e),
            },
        )


# ============================================================================
# Batch Drawing Operations
# ============================================================================


async def create_drawings_batch_impl(app: "IAppContext", drawings: list[dict]) -> str:
    """Create multiple drawing objects in batch with validation

    Two-phase execution:
    1. VALIDATE ALL drawings (check required params, valid types)
    2. CREATE ALL drawings (only if all valid, sequential execution)

    Args:
        app: Application context
        drawings: List of drawing dicts, each containing:
            {
                "drawing_type": "rectangle" | "ellipse" | "line" | "text",
                "x": int,
                "y": int,
                "z": int (optional),
                ...type-specific parameters
            }

            Drawing types and their parameters:

            - "rectangle": Rectangle drawing
                x (int): Top-left X coordinate
                y (int): Top-left Y coordinate
                width (int): Rectangle width (required)
                height (int): Rectangle height (required)
                fill_color (str, optional): Fill color (default: "#ffffff")
                border_color (str, optional): Border color (default: "#000000")
                border_width (int, optional): Border width in pixels (default: 2)
                z (int, optional): Z-order/layer (default: 0)

            - "ellipse": Ellipse/circle drawing
                x (int): Top-left X coordinate
                y (int): Top-left Y coordinate
                rx (int): Horizontal radius (required)
                ry (int): Vertical radius (required)
                fill_color (str, optional): Fill color (default: "#ffffff")
                border_color (str, optional): Border color (default: "#000000")
                border_width (int, optional): Border width in pixels (default: 2)
                z (int, optional): Z-order/layer (default: 0)

            - "line": Line drawing
                x (int): Start X coordinate
                y (int): Start Y coordinate
                x2 (int): X offset from start (required)
                y2 (int): Y offset from start (required)
                color (str, optional): Line color (default: "#000000")
                border_width (int, optional): Line width in pixels (default: 2)
                z (int, optional): Z-order/layer (default: 0)

            - "text": Text label
                x (int): Text X coordinate
                y (int): Text Y coordinate
                text (str): Text content (required)
                font_size (int, optional): Font size in points (default: 10)
                font_weight (str, optional): Font weight (default: "normal")
                font_family (str, optional): Font family (default: "TypeWriter")
                color (str, optional): Text color (default: "#000000")
                z (int, optional): Z-order/layer (default: 1)

    Returns:
        JSON with execution results:
        {
            "completed": [0, 1, 2],  // Indices of successful drawings
            "failed": [3],  // Indices of failed drawings
            "results": [
                {
                    "drawing_index": 0,
                    "success": true,
                    "drawing_type": "rectangle",
                    "drawing_id": "abc-123-def",
                    "result": {...}  // Drawing info
                },
                ...
            ],
            "total_drawings": 4,
            "execution_time": 2.3
        }

    Examples:
        # Create multiple shapes:
        create_drawings_batch([
            {"drawing_type": "rectangle", "x": 100, "y": 100, "width": 200, "height": 100},
            {"drawing_type": "ellipse", "x": 400, "y": 100, "rx": 50, "ry": 50},
            {"drawing_type": "line", "x": 100, "y": 250, "x2": 300, "y2": 0}
        ])

        # Create labeled diagram:
        create_drawings_batch([
            {"drawing_type": "rectangle", "x": 100, "y": 100, "width": 150, "height": 80, "z": 0},
            {"drawing_type": "text", "x": 175, "y": 140, "text": "Router1", "z": 1}
        ])
    """
    import time

    start_time = time.time()

    # Validation: Check all drawings first
    VALID_TYPES = {"rectangle", "ellipse", "line", "text"}

    for idx, drawing in enumerate(drawings):
        # Check required fields
        if "drawing_type" not in drawing:
            return validation_error(
                parameter="drawings",
                details=f"Drawing {idx} missing required field 'drawing_type'",
                valid_values=list(VALID_TYPES),
            )

        drawing_type = drawing["drawing_type"].lower()
        if drawing_type not in VALID_TYPES:
            return validation_error(
                parameter=f"drawings[{idx}].drawing_type",
                details=f"Invalid drawing type: {drawing['drawing_type']}",
                valid_values=list(VALID_TYPES),
            )

        if "x" not in drawing:
            return create_error_response(
                error=f"Drawing {idx} missing required field 'x'",
                error_code=ErrorCode.MISSING_PARAMETER.value,
                details="All drawings must specify 'x' coordinate",
                suggested_action="Add 'x' field to drawing",
                context={"drawing_index": idx, "drawing": drawing},
            )

        if "y" not in drawing:
            return create_error_response(
                error=f"Drawing {idx} missing required field 'y'",
                error_code=ErrorCode.MISSING_PARAMETER.value,
                details="All drawings must specify 'y' coordinate",
                suggested_action="Add 'y' field to drawing",
                context={"drawing_index": idx, "drawing": drawing},
            )

        # Type-specific validation
        if drawing_type == "rectangle":
            if "width" not in drawing or "height" not in drawing:
                return create_error_response(
                    error=f"Drawing {idx} (type='rectangle') missing required parameters",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Rectangle requires 'width' and 'height' parameters",
                    suggested_action="Add width and height fields to drawing",
                    context={"drawing_index": idx, "drawing_type": drawing_type},
                )

        elif drawing_type == "ellipse":
            if "rx" not in drawing or "ry" not in drawing:
                return create_error_response(
                    error=f"Drawing {idx} (type='ellipse') missing required parameters",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Ellipse requires 'rx' and 'ry' parameters",
                    suggested_action="Add rx and ry fields to drawing",
                    context={"drawing_index": idx, "drawing_type": drawing_type},
                )

        elif drawing_type == "line":
            if "x2" not in drawing or "y2" not in drawing:
                return create_error_response(
                    error=f"Drawing {idx} (type='line') missing required parameters",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Line requires 'x2' and 'y2' parameters",
                    suggested_action="Add x2 and y2 fields to drawing",
                    context={"drawing_index": idx, "drawing_type": drawing_type},
                )

        elif drawing_type == "text":
            if "text" not in drawing:
                return create_error_response(
                    error=f"Drawing {idx} (type='text') missing required parameter",
                    error_code=ErrorCode.MISSING_PARAMETER.value,
                    details="Text drawing requires 'text' parameter",
                    suggested_action="Add text field to drawing",
                    context={"drawing_index": idx, "drawing_type": drawing_type},
                )

    # Validation passed - create all drawings sequentially
    results = []
    completed_indices = []
    failed_indices = []

    for idx, drawing in enumerate(drawings):
        drawing_type = drawing["drawing_type"]

        try:
            # Execute drawing creation with all parameters
            result = await create_drawing_impl(
                app,
                drawing_type=drawing_type,
                x=drawing["x"],
                y=drawing["y"],
                z=drawing.get("z", 0),
                # Rectangle/Ellipse parameters
                width=drawing.get("width"),
                height=drawing.get("height"),
                rx=drawing.get("rx"),
                ry=drawing.get("ry"),
                fill_color=drawing.get("fill_color", "#ffffff"),
                border_color=drawing.get("border_color", "#000000"),
                border_width=drawing.get("border_width", 2),
                # Line parameters
                x2=drawing.get("x2"),
                y2=drawing.get("y2"),
                # Text parameters
                text=drawing.get("text"),
                font_size=drawing.get("font_size", 10),
                font_weight=drawing.get("font_weight", "normal"),
                font_family=drawing.get("font_family", "TypeWriter"),
                color=drawing.get("color", "#000000"),
            )

            # Parse result to extract drawing_id
            result_data = json.loads(result) if isinstance(result, str) else result
            drawing_id = result_data.get("drawing_id")

            # Drawing created successfully
            results.append(
                {
                    "drawing_index": idx,
                    "success": True,
                    "drawing_type": drawing_type,
                    "drawing_id": drawing_id,
                    "result": result_data,
                }
            )
            completed_indices.append(idx)

        except Exception as e:
            # Drawing creation failed
            results.append(
                {
                    "drawing_index": idx,
                    "success": False,
                    "drawing_type": drawing_type,
                    "error": str(e),
                }
            )
            failed_indices.append(idx)

    execution_time = time.time() - start_time

    return json.dumps(
        {
            "completed": completed_indices,
            "failed": failed_indices,
            "results": results,
            "total_drawings": len(drawings),
            "execution_time": round(execution_time, 2),
        },
        indent=2,
    )
