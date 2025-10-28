"""Topology Export Tools

SVG/PNG diagram generation for GNS3 network topologies.
Extracted from main.py v0.9.1 for better modularity.
"""

import base64
import json
import re
from typing import Optional

from mcp.server.fastmcp import Context
from models import ErrorResponse


def add_font_fallbacks(style_string: str) -> str:
    """
    Add CSS-style font fallbacks to SVG style strings for consistent rendering.

    Ensures consistent font appearance across different systems by adding fallback
    fonts when a single font family is specified. Qt (used by GNS3 GUI) handles
    font fallback automatically, but SVG renderers need explicit fallback chains.

    Args:
        style_string: SVG style string (e.g., "font-family: TypeWriter;font-size: 10;")

    Returns:
        Modified style string with fallback fonts added

    Examples:
        >>> add_font_fallbacks("font-family: TypeWriter;font-size: 10;")
        "font-family: TypeWriter, 'Courier New', Courier, 'Liberation Mono', Consolas, monospace;font-size: 10;"

        >>> add_font_fallbacks("font-family: Gerbera Black;font-size: 22;")
        "font-family: 'Gerbera Black', Georgia, 'Times New Roman', serif;font-size: 22;"
    """
    if not style_string or "font-family:" not in style_string:
        return style_string

    # Parse style string into key-value pairs
    parts = []
    for part in style_string.split(";"):
        if not part.strip():
            continue

        if ":" in part:
            key, val = part.split(":", 1)
            key = key.strip()
            val = val.strip()

            if key == "font-family":
                # Check if already has fallbacks (contains comma)
                if "," in val:
                    parts.append(f"{key}: {val}")
                else:
                    # Single font - add fallbacks based on font type
                    font_name = val.strip()

                    # TypeWriter and monospace fonts
                    if font_name.lower() in ["typewriter", "courier", "monaco", "consolas"]:
                        fallback = f"{font_name}, 'Courier New', Courier, 'Liberation Mono', Consolas, monospace"
                    # Decorative/Display fonts
                    elif "gerbera" in font_name.lower() or "black" in font_name.lower():
                        # Quote font names with spaces
                        if " " in font_name:
                            font_name = f"'{font_name}'"
                        fallback = f"{font_name}, Georgia, 'Times New Roman', serif"
                    # Sans-serif fonts
                    elif any(x in font_name.lower() for x in ["arial", "helvetica", "verdana", "sans"]):
                        fallback = f"{font_name}, Arial, Helvetica, 'Liberation Sans', sans-serif"
                    # Default: assume serif
                    else:
                        fallback = f"{font_name}, Georgia, 'Times New Roman', serif"

                    parts.append(f"{key}: {fallback}")
            else:
                parts.append(f"{key}: {val}")
        else:
            parts.append(part.strip())

    return ";".join(parts) + ";" if parts else style_string


# SVG Generation Helpers

def create_rectangle_svg(width: int, height: int, fill: str = "#ffffff",
                        border: str = "#000000", border_width: int = 2) -> str:
    """Generate SVG for a rectangle"""
    return f'''<svg height="{height}" width="{width}">
  <rect fill="{fill}" fill-opacity="1.0" height="{height}" width="{width}"
        stroke="{border}" stroke-width="{border_width}" />
</svg>'''


def create_text_svg(text: str, font_size: int = 10, font_weight: str = "normal",
                   font_family: str = "TypeWriter", color: str = "#000000") -> str:
    """Generate SVG for text

    Uses GNS3-compatible dimensions for TypeWriter monospace font:
    - Width: ~0.9 * font_size per character (e.g., "test" at size 10 = 35px)
    - Height: ~2.4 * font_size (e.g., size 10 = 24px)
    """
    # Escape XML special characters
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Calculate dimensions matching GNS3's text rendering
    # TypeWriter monospace: ~0.9 pixels per character per font size point
    width = int(len(text) * font_size * 0.9)
    height = int(font_size * 2.4)

    return f'''<svg width="{width}" height="{height}"><text font-family="{font_family}" font-size="{font_size}" font-weight="{font_weight}" fill="{color}" fill-opacity="1.0">{text}</text></svg>'''


def create_ellipse_svg(rx: int, ry: int, fill: str = "#ffffff",
                      border: str = "#000000", border_width: int = 2) -> str:
    """Generate SVG for an ellipse"""
    width = rx * 2
    height = ry * 2
    return f'''<svg height="{height}" width="{width}">
  <ellipse cx="{rx}" cy="{ry}" fill="{fill}" fill-opacity="1.0"
           rx="{rx}" ry="{ry}" stroke="{border}" stroke-width="{border_width}" />
</svg>'''


def create_line_svg(x2: int, y2: int, stroke: str = "#000000", stroke_width: int = 2) -> str:
    """Generate SVG for a line

    Args:
        x2: X coordinate of end point (relative to x, y position)
        y2: Y coordinate of end point (relative to x, y position)
        stroke: Line color
        stroke_width: Line width in pixels

    Note: Line starts at (0, 0) in SVG, which maps to the drawing's (x, y) position.
          End point is at (x2, y2) relative to start.
    """
    # Calculate SVG dimensions to fit the line
    width = abs(x2) + stroke_width
    height = abs(y2) + stroke_width

    # Adjust start/end points if line goes in negative direction
    x1 = stroke_width // 2 if x2 >= 0 else abs(x2) + stroke_width // 2
    y1 = stroke_width // 2 if y2 >= 0 else abs(y2) + stroke_width // 2
    x2_adj = x1 + x2
    y2_adj = y1 + y2

    return f'''<svg height="{height}" width="{width}">
  <line stroke="{stroke}" stroke-width="{stroke_width}" stroke-linecap="round"
        x1="{x1}" y1="{y1}" x2="{x2_adj}" y2="{y2_adj}" />
</svg>'''


# MCP Tool

async def export_topology_diagram(ctx: Context, output_path: str,
                                  format: str = "both",
                                  crop_x: Optional[int] = None,
                                  crop_y: Optional[int] = None,
                                  crop_width: Optional[int] = None,
                                  crop_height: Optional[int] = None) -> str:
    """Export topology as SVG and/or PNG diagram (returns JSON with file paths and diagram info)

    Creates a visual diagram of the current topology including nodes, links,
    and drawings with status indicators.

    GNS3 Coordinate System:
    - Node positions (x, y): Top-left corner of icon
    - Node icon sizes: PNG images = 78×78, SVG/internal icons = 58×58
    - Label positions: Stored as offsets from node center in GNS3
    - Link connections: Connect to node centers (x + icon_size/2, y + icon_size/2)
    - Drawing positions (x, y): Top-left corner

    Args:
        output_path: Base path for output files (without extension)
        format: Output format - "svg", "png", or "both" (default: "both")
        crop_x: Optional crop X coordinate (default: auto-fit to content)
        crop_y: Optional crop Y coordinate (default: auto-fit to content)
        crop_width: Optional crop width (default: auto-fit to content)
        crop_height: Optional crop height (default: auto-fit to content)

    Returns:
        JSON with created file paths and diagram info
    """
    # Import here to avoid circular dependency
    import logging

    from main import validate_current_project

    logger = logging.getLogger(__name__)
    app = ctx.request_context.lifespan_context

    error = await validate_current_project(app)
    if error:
        return error

    try:
        # Get all topology data
        nodes = await app.gns3.get_nodes(app.current_project_id)
        links = await app.gns3.get_links(app.current_project_id)
        drawings = await app.gns3.get_drawings(app.current_project_id)

        # Calculate bounds
        if crop_x is None or crop_y is None or crop_width is None or crop_height is None:
            # Check if project is empty
            if not nodes and not drawings:
                return json.dumps(ErrorResponse(
                    error="Cannot export empty project",
                    details="Project has no nodes or drawings to export. Add some nodes first.",
                    suggested_action="Create nodes in your project using create_node() or the GNS3 GUI before exporting"
                ).model_dump(), indent=2)

            # Auto-calculate bounds
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')

            for node in nodes:
                x, y = node['x'], node['y']
                symbol = node.get('symbol', '')

                # Determine icon size: PNG = 78×78, SVG = 58×58
                if symbol and symbol.lower().endswith('.png'):
                    icon_size = 78
                else:
                    icon_size = 58

                # Get label position to account for it in bounds
                label_info = node.get('label', {})
                label_x = label_info.get('x', 0)
                label_y = label_info.get('y', icon_size // 2 + 20)

                # Account for node icon (top-left at x,y)
                min_x = min(min_x, x)
                max_x = max(max_x, x + icon_size)
                min_y = min(min_y, y)
                max_y = max(max_y, y + icon_size)

                # Account for label position (relative to node top-left)
                label_abs_x = x + label_x
                label_abs_y = y + label_y
                min_x = min(min_x, label_abs_x - 50)  # Approximate text width
                max_x = max(max_x, label_abs_x + 50)
                min_y = min(min_y, label_abs_y - 10)  # Approximate text height
                max_y = max(max_y, label_abs_y + 10)

            for drawing in drawings:
                # Parse SVG to get dimensions (basic parsing)
                svg = drawing['svg']
                if 'width=' in svg and 'height=' in svg:
                    w_match = re.search(r'width="(\d+)"', svg)
                    h_match = re.search(r'height="(\d+)"', svg)
                    if w_match and h_match:
                        w, h = int(w_match.group(1)), int(h_match.group(1))
                        min_x = min(min_x, drawing['x'])
                        max_x = max(max_x, drawing['x'] + w)
                        min_y = min(min_y, drawing['y'])
                        max_y = max(max_y, drawing['y'] + h)

            # Add padding
            padding = 50
            crop_x = int(min_x - padding)
            crop_y = int(min_y - padding)
            crop_width = int(max_x - min_x + padding * 2)
            crop_height = int(max_y - min_y + padding * 2)

        # Generate SVG
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{crop_width}" height="{crop_height}"
     viewBox="{crop_x} {crop_y} {crop_width} {crop_height}">

  <!-- CSS Styles -->
  <style>
    .node-label {{
      dominant-baseline: text-before-edge;
    }}
    .link {{
      stroke-width: 2;
    }}
    .link-active {{
      stroke: #00aa00;
    }}
    .link-stopped {{
      stroke: #808080;
    }}
    .port-indicator {{
      stroke: #000000;
      stroke-width: 1;
    }}
  </style>

'''

        # Build list of items to render with z-order
        render_items = []  # List of (z_value, type, svg_fragment)

        # 1. Add DRAWINGS to render list
        for drawing in drawings:
            x, y = drawing['x'], drawing['y']
            z = drawing.get('z', 0)
            svg = drawing['svg']

            # Embed drawing SVG at position
            drawing_svg = f'  <!-- Drawing at ({x}, {y}) -->\n'
            drawing_svg += f'  <g transform="translate({x}, {y})">\n'
            drawing_svg += f'    {svg}\n'
            drawing_svg += '  </g>\n'

            render_items.append((z, 'drawing', drawing_svg))

        # 2. Add LINKS to render list
        # Links render at z = min(connected_nodes_z) - 0.5 (always below nodes)
        node_z_map = {n['name']: n.get('z', 1) for n in nodes}

        for link in links:
            link_nodes = link.get('nodes', [])
            if len(link_nodes) != 2:
                continue

            node_a = link_nodes[0]
            node_b = link_nodes[1]

            # Find node details
            node_a_data = next((n for n in nodes if n['node_id'] == node_a['node_id']), None)
            node_b_data = next((n for n in nodes if n['node_id'] == node_b['node_id']), None)

            if not node_a_data or not node_b_data:
                continue

            # Get node positions and icon sizes
            ax, ay = node_a_data['x'], node_a_data['y']
            bx, by = node_b_data['x'], node_b_data['y']

            symbol_a = node_a_data.get('symbol', '')
            symbol_b = node_b_data.get('symbol', '')

            icon_size_a = 78 if symbol_a.lower().endswith('.png') else 58
            icon_size_b = 78 if symbol_b.lower().endswith('.png') else 58

            # Links connect to node centers
            ax_center = ax + icon_size_a / 2
            ay_center = ay + icon_size_a / 2
            bx_center = bx + icon_size_b / 2
            by_center = by + icon_size_b / 2

            # Determine link status (active if both nodes started and link not suspended)
            status_a = node_a_data.get('status', 'stopped')
            status_b = node_b_data.get('status', 'stopped')
            link_suspended = link.get('suspend', False)

            link_active = (status_a == 'started' and status_b == 'started' and not link_suspended)
            link_class = "link-active" if link_active else "link-stopped"

            # Calculate z-value for link (min of connected nodes - 0.5)
            z_a = node_z_map.get(node_a_data['name'], 1)
            z_b = node_z_map.get(node_b_data['name'], 1)
            link_z = min(z_a, z_b) - 0.5

            # Build link SVG
            link_svg = f'  <!-- Link: {node_a_data["name"]} <-> {node_b_data["name"]} -->\n'
            link_svg += f'  <line class="link {link_class}" x1="{ax_center}" y1="{ay_center}" x2="{bx_center}" y2="{by_center}"/>\n'

            # Add port status indicators (circles at connection points)
            color_a = "#00aa00" if status_a == 'started' and not link_suspended else "#ff0000"
            color_b = "#00aa00" if status_b == 'started' and not link_suspended else "#ff0000"

            # Calculate indicator positions (slightly offset from node center toward link)
            dx, dy = bx_center - ax_center, by_center - ay_center
            length = (dx**2 + dy**2)**0.5
            if length > 0:
                dx_norm, dy_norm = dx / length, dy / length
                offset = icon_size_a / 2  # Place at edge of node

                ind_ax = ax_center + dx_norm * offset
                ind_ay = ay_center + dy_norm * offset
                ind_bx = bx_center - dx_norm * (icon_size_b / 2)
                ind_by = by_center - dy_norm * (icon_size_b / 2)

                link_svg += f'  <circle cx="{ind_ax}" cy="{ind_ay}" r="4" fill="{color_a}"/>\n'
                link_svg += f'  <circle cx="{ind_bx}" cy="{ind_by}" r="4" fill="{color_b}"/>\n'

            # Store link in render list with calculated z-value
            render_items.append((link_z, 'link', link_svg))

        # 3. Add NODES to render list
        for node in nodes:
            x, y = node['x'], node['y']
            status = node['status']
            name = node['name']
            symbol = node.get('symbol', '')

            # Determine icon size based on symbol type
            # PNG images: 78×78, SVG/internal icons: 58×58
            if symbol and symbol.lower().endswith('.png'):
                icon_size = 78
            else:
                icon_size = 58

            # Fetch actual icon if available
            icon_data = None
            if symbol:
                try:
                    # Get raw symbol data from GNS3
                    raw_bytes = await app.gns3.get_symbol_raw(symbol)

                    # Determine MIME type
                    if symbol.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif symbol.lower().endswith('.svg'):
                        mime_type = 'image/svg+xml'
                    elif symbol.lower().endswith('.jpg') or symbol.lower().endswith('.jpeg'):
                        mime_type = 'image/jpeg'
                    else:
                        mime_type = 'image/png'  # Default

                    # Encode as base64 data URI
                    b64_data = base64.b64encode(raw_bytes).decode('utf-8')
                    icon_data = f"data:{mime_type};base64,{b64_data}"

                except Exception as e:
                    logger.warning(f"Failed to fetch icon for {symbol}: {e}")
                    icon_data = None

            # Try category-based fallback if primary icon failed
            if not icon_data:
                # Map node_type to category fallback icons
                node_type = node.get('node_type', '')
                fallback_symbol = None

                if node_type == 'qemu':
                    # Most QEMU nodes are routers
                    fallback_symbol = ':/symbols/affinity/circle/blue/router.svg'
                elif node_type in ['ethernet_switch', 'ethernet_hub', 'atm_switch', 'frame_relay_switch']:
                    fallback_symbol = ':/symbols/affinity/square/blue/switch_multilayer.svg'
                elif node_type in ['nat', 'vpcs', 'cloud', 'docker']:
                    fallback_symbol = ':/symbols/classic/computer.svg'
                else:
                    fallback_symbol = ':/symbols/affinity/circle/blue/router.svg'  # Default

                # Try to fetch category fallback icon
                if fallback_symbol:
                    try:
                        raw_bytes = await app.gns3.get_symbol_raw(fallback_symbol)
                        b64_data = base64.b64encode(raw_bytes).decode('utf-8')
                        icon_data = f"data:image/svg+xml;base64,{b64_data}"
                    except Exception as e:
                        logger.warning(f"Failed to fetch fallback icon {fallback_symbol}: {e}")
                        icon_data = None

            # Extract label information from GNS3 data
            # GNS3 stores label offset from node top-left to label box top-left
            label_info = node.get('label', {})
            label_text = label_info.get('text', name)
            label_x_offset = label_info.get('x', 0)
            label_y_offset = label_info.get('y', icon_size//2 + 20)
            label_rotation = label_info.get('rotation', 0)
            label_style = label_info.get('style', '')

            # Extract font size from style, default to 10
            font_size = 10.0
            if label_style:
                font_match = re.search(r'font-size:\s*(\d+\.?\d*)', label_style)
                if font_match:
                    font_size = float(font_match.group(1))

            # GNS3 Label Positioning:
            # - When x is None, GNS3 auto-centers the label above the node
            # - When x/y are set, they represent the label position directly (not bounding box)
            # - Official GNS3 uses text position, not bounding box corner
            if label_x_offset is None:
                # Auto-center label above node (mimic official GNS3 behavior)
                estimated_width = len(label_text) * font_size * 0.6
                label_x = icon_size / 2  # Center of node
                label_y = -25  # Standard position above node
                text_anchor = "middle"
            else:
                # Manual positioning - use stored position directly
                label_x = label_x_offset
                label_y = label_y_offset

                # Determine text anchor based on position relative to node center
                if abs(label_x_offset - icon_size / 2) < 5:
                    text_anchor = "middle"  # Centered
                elif label_x_offset > icon_size / 2:
                    text_anchor = "end"  # Right of center (right-aligned)
                else:
                    text_anchor = "start"  # Left of center (left-aligned)

            # Apply font fallbacks to label style
            if label_style:
                label_style = add_font_fallbacks(label_style)

            # Build node SVG
            node_svg = f'  <!-- Node: {name} ({status}) -->\n'
            node_svg += f'  <g transform="translate({x}, {y})">\n'

            # Add node icon (if available)
            if icon_data:
                node_svg += f'    <image href="{icon_data}" width="{icon_size}" height="{icon_size}"/>\n'
            else:
                # Fallback: colored rectangle
                status_class = f"node-{status}"
                color = {"started": "#00aa00", "stopped": "#ff0000", "suspended": "#ffaa00"}.get(status, "#808080")
                node_svg += f'    <rect width="{icon_size}" height="{icon_size}" fill="{color}" stroke="#000000" stroke-width="2"/>\n'
                node_svg += f'    <text x="{icon_size/2}" y="{icon_size/2}" text-anchor="middle" dominant-baseline="middle" fill="#ffffff">{name[:8]}</text>\n'

            # Add label
            label_transform = f'rotate({label_rotation} {label_x} {label_y})' if label_rotation != 0 else ''
            node_svg += f'    <text class="node-label" x="{label_x}" y="{label_y}" text-anchor="{text_anchor}" transform="{label_transform}" style="{label_style}">{label_text}</text>\n'

            node_svg += '  </g>\n'

            # Store node in render list
            node_z = node.get('z', 1)
            render_items.append((node_z, 'node', node_svg))

        # Sort by z-order and render
        sorted_items = sorted(render_items, key=lambda item: item[0])

        for z_value, item_type, svg_fragment in sorted_items:
            svg_content += svg_fragment

        svg_content += '</svg>\n'

        # Save SVG
        files_created = []
        if format in ["svg", "both"]:
            svg_path = f"{output_path}.svg"
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            files_created.append(svg_path)

        # Save PNG (if requested and cairosvg available)
        if format in ["png", "both"]:
            try:
                import cairosvg
                png_path = f"{output_path}.png"
                cairosvg.svg2png(bytestring=svg_content.encode('utf-8'),
                               write_to=png_path)
                files_created.append(png_path)
            except ImportError:
                return json.dumps({
                    "warning": "PNG export requires cairosvg library",
                    "files_created": files_created,
                    "bounds": {"x": crop_x, "y": crop_y, "width": crop_width, "height": crop_height},
                    "note": "Install with: pip install cairosvg"
                }, indent=2)

        return json.dumps({
            "message": "Topology diagram exported successfully",
            "files_created": files_created,
            "bounds": {"x": crop_x, "y": crop_y, "width": crop_width, "height": crop_height},
            "nodes_count": len(nodes),
            "links_count": len(links),
            "drawings_count": len(drawings)
        }, indent=2)

    except Exception as e:
        return json.dumps(ErrorResponse(
            error="Failed to export topology diagram",
            details=str(e)
        ).model_dump(), indent=2)
