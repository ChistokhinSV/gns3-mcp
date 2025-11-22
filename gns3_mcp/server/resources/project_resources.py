"""
Project-related MCP Resources

Handles resources for projects, nodes, links, templates, and drawings.
"""

import json
from typing import TYPE_CHECKING, Any, Dict, List

from tabulate import tabulate

if TYPE_CHECKING:
    from interfaces import IAppContext


def format_table(data: List[Dict[str, Any]], columns: List[str]) -> str:
    """Format list of dicts as simple text table

    Args:
        data: List of dictionaries containing data
        columns: List of column names to include in output

    Returns:
        Formatted table string with "simple" style (no borders)
    """
    if not data:
        return "No items found"

    # Extract specified columns from each dict
    rows = [[item.get(col, "") for col in columns] for item in data]
    return tabulate(rows, headers=columns, tablefmt="simple")


async def list_projects_impl(app: "IAppContext", detailed: bool = False) -> str:
    """
    List all GNS3 projects with their statuses and URIs

    Resource URI: projects://

    Args:
        detailed: If False (default), return table format with uri field.
                  If True, return full project data as JSON from GNS3 API.

    Returns:
        Formatted text table of project summaries (default) or JSON (detailed=True)
    """
    try:
        projects = await app.gns3.get_projects()

        if detailed:
            # Return full data from GNS3 API as JSON
            return json.dumps(projects, indent=2)
        else:
            # Return formatted table with ProjectSummary data
            from models import ProjectSummary

            summaries = [
                ProjectSummary(
                    status=p["status"], name=p["name"], project_id=p["project_id"]
                ).model_dump()
                for p in projects
            ]
            return format_table(summaries, columns=["status", "name", "uri"])
    except Exception as e:
        return f"Error: Failed to list projects\nDetails: {str(e)}"


async def get_project_impl(app: "IAppContext", project_id: str) -> str:
    """
    Get project details by ID

    Resource URI: projects://{project_id}

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON object with project details
    """
    try:
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        return json.dumps(project, indent=2)
    except Exception as e:
        return json.dumps(
            {"error": "Failed to get project", "project_id": project_id, "details": str(e)},
            indent=2,
        )


async def list_nodes_impl(app: "IAppContext", project_id: str) -> str:
    """
    List all nodes in a project

    Resource URI: projects://{project_id}/nodes/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of node summaries
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        # Get nodes
        nodes = await app.gns3.get_nodes(project_id)

        # Return formatted table with NodeSummary data
        from models import NodeSummary

        summaries = [
            NodeSummary(
                project_id=project_id,
                node_id=n["node_id"],
                name=n["name"],
                node_type=n["node_type"],
                status=n["status"],
                console_type=n["console_type"],
                console=n.get("console"),
            ).model_dump()
            for n in nodes
        ]

        return format_table(
            summaries, columns=["name", "node_type", "status", "console_type", "console", "uri"]
        )
    except Exception as e:
        return f"Error: Failed to list nodes in project {project_id}\nDetails: {str(e)}"


async def get_node_impl(app: "IAppContext", project_id: str, node_id: str) -> str:
    """
    Get detailed node information

    Resource URI: projects://{project_id}/nodes/{node_id}

    Args:
        project_id: GNS3 project UUID
        node_id: Node UUID

    Returns:
        JSON object with complete node details (NodeInfo)
    """
    try:
        # Get all nodes
        nodes = await app.gns3.get_nodes(project_id)
        node = next((n for n in nodes if n["node_id"] == node_id), None)

        if not node:
            return json.dumps(
                {"error": "Node not found", "project_id": project_id, "node_id": node_id}, indent=2
            )

        # Return full NodeInfo format
        from models import NodeInfo

        props = node.get("properties", {})
        info = NodeInfo(
            node_id=node["node_id"],
            name=node["name"],
            node_type=node["node_type"],
            status=node["status"],
            console_type=node["console_type"],
            console=node.get("console"),
            console_host=node.get("console_host"),
            compute_id=node.get("compute_id", "local"),
            x=node.get("x", 0),
            y=node.get("y", 0),
            z=node.get("z", 0),
            locked=node.get("locked", False),
            ports=node.get("ports"),
            label=node.get("label"),
            symbol=node.get("symbol"),
            ram=props.get("ram"),
            cpus=props.get("cpus"),
            adapters=props.get("adapters"),
            hdd_disk_image=props.get("hdd_disk_image"),
            hda_disk_image=props.get("hda_disk_image"),
        ).model_dump()

        return json.dumps(info, indent=2)
    except Exception as e:
        return json.dumps(
            {
                "error": "Failed to get node",
                "project_id": project_id,
                "node_id": node_id,
                "details": str(e),
            },
            indent=2,
        )


async def list_links_impl(app: "IAppContext", project_id: str) -> str:
    """
    List all network links in a project

    Resource URI: projects://{project_id}/links/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of link information with adapter/port details
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        # Get links and nodes
        links = await app.gns3.get_links(project_id)
        nodes = await app.gns3.get_nodes(project_id)

        # Build node lookup
        node_lookup = {n["node_id"]: n for n in nodes}

        # Build link info with port names
        from models import LinkInfo

        link_infos = []

        for link in links:
            nodes_data = link.get("nodes", [])
            if len(nodes_data) >= 2:
                node_a_id = nodes_data[0].get("node_id")
                node_b_id = nodes_data[1].get("node_id")
                node_a = node_lookup.get(node_a_id)
                node_b = node_lookup.get(node_b_id)

                if node_a and node_b:
                    # Get port names from node ports
                    port_a_num = nodes_data[0].get("port_number", 0)
                    port_b_num = nodes_data[1].get("port_number", 0)
                    adapter_a_num = nodes_data[0].get("adapter_number", 0)
                    adapter_b_num = nodes_data[1].get("adapter_number", 0)

                    port_a_name = None
                    port_b_name = None

                    if node_a.get("ports"):
                        for port in node_a["ports"]:
                            if (
                                port.get("adapter_number") == adapter_a_num
                                and port.get("port_number") == port_a_num
                            ):
                                port_a_name = port.get("name")
                                break

                    if node_b.get("ports"):
                        for port in node_b["ports"]:
                            if (
                                port.get("adapter_number") == adapter_b_num
                                and port.get("port_number") == port_b_num
                            ):
                                port_b_name = port.get("name")
                                break

                    # Build LinkEndpoint objects
                    from models import LinkEndpoint

                    endpoint_a = LinkEndpoint(
                        node_id=node_a_id,
                        node_name=node_a["name"],
                        adapter_number=adapter_a_num,
                        port_number=port_a_num,
                        port_name=port_a_name,
                    )

                    endpoint_b = LinkEndpoint(
                        node_id=node_b_id,
                        node_name=node_b["name"],
                        adapter_number=adapter_b_num,
                        port_number=port_b_num,
                        port_name=port_b_name,
                    )

                    link_info = LinkInfo(
                        link_id=link["link_id"],
                        link_type=link.get("link_type", "ethernet"),
                        node_a=endpoint_a,
                        node_b=endpoint_b,
                        capturing=link.get("capturing", False),
                        capture_file_name=link.get("capture_file_name"),
                        capture_file_path=link.get("capture_file_path"),
                        capture_compute_id=link.get("capture_compute_id"),
                        suspend=link.get("suspend", False),
                    ).model_dump()

                    link_infos.append(link_info)

        return json.dumps(link_infos, indent=2)
    except Exception as e:
        return json.dumps(
            {"error": "Failed to list links", "project_id": project_id, "details": str(e)}, indent=2
        )


async def list_templates_impl(app: "IAppContext") -> str:
    """
    List available GNS3 templates

    Resource URI: templates://

    Returns:
        Formatted text table of template information (excludes compute_id, symbol, usage)
    """
    try:
        templates = await app.gns3.get_templates()

        # Build template info using list view (hides compute_id, symbol, usage)
        from models import TemplateInfo

        template_infos = [
            TemplateInfo(
                template_id=t["template_id"],
                name=t["name"],
                category=t.get("category", "guest"),
                node_type=t.get("template_type"),
                builtin=t.get("builtin", False),
                compute_id=t.get("compute_id", "local"),
                symbol=t.get("symbol"),
            ).to_list_view()
            for t in templates
        ]

        return format_table(
            template_infos, columns=["name", "category", "node_type", "builtin", "uri"]
        )
    except Exception as e:
        return f"Error: Failed to list templates\nDetails: {str(e)}"


async def get_template_impl(app: "IAppContext", template_id: str) -> str:
    """
    Get template details including usage notes

    Resource URI: gns3://templates/{template_id}

    Args:
        template_id: Template UUID

    Returns:
        JSON object with full template details including usage field
        (credentials, setup instructions, persistent storage notes)
    """
    try:
        template = await app.gns3.get_template(template_id)

        from models import TemplateInfo

        template_info = TemplateInfo(
            template_id=template["template_id"],
            name=template["name"],
            category=template.get("category", "guest"),
            node_type=template.get("template_type"),
            builtin=template.get("builtin", False),
            compute_id=template.get("compute_id", "local"),
            symbol=template.get("symbol"),
            usage=template.get("usage", ""),  # Includes credentials/setup instructions
        )

        return json.dumps(template_info.to_detail_view(), indent=2)
    except Exception as e:
        return json.dumps(
            {"error": "Failed to get template", "template_id": template_id, "details": str(e)},
            indent=2,
        )


async def get_node_template_usage_impl(app: "IAppContext", project_id: str, node_id: str) -> str:
    """
    Get template usage notes for a specific node

    Resource URI: projects://{project_id}/nodes/{node_id}/template

    Args:
        project_id: GNS3 project UUID
        node_id: Node UUID

    Returns:
        JSON object with template details and usage notes for the node's template
    """
    try:
        nodes = await app.gns3.get_nodes(project_id)
        node = next((n for n in nodes if n["node_id"] == node_id), None)

        if not node:
            return json.dumps(
                {"error": "Node not found", "project_id": project_id, "node_id": node_id}, indent=2
            )

        template_id = node.get("template_id")
        if not template_id:
            return json.dumps(
                {
                    "error": "Node has no associated template",
                    "node_id": node_id,
                    "node_name": node.get("name"),
                },
                indent=2,
            )

        # Get template with usage
        template = await app.gns3.get_template(template_id)

        return json.dumps(
            {
                "node_id": node_id,
                "node_name": node.get("name"),
                "template_id": template_id,
                "template_name": template["name"],
                "usage": template.get("usage", ""),
                "category": template.get("category"),
                "node_type": template.get("template_type"),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {
                "error": "Failed to get node template usage",
                "project_id": project_id,
                "node_id": node_id,
                "details": str(e),
            },
            indent=2,
        )


async def list_drawings_impl(app: "IAppContext", project_id: str) -> str:
    """
    List all drawing objects in a project

    Resource URI: projects://{project_id}/drawings/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of drawing information
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        # Get drawings
        drawings = await app.gns3.get_drawings(project_id)

        # Build drawing info
        from models import DrawingInfo

        drawing_infos = [
            DrawingInfo(
                drawing_id=d["drawing_id"],
                x=d.get("x", 0),
                y=d.get("y", 0),
                z=d.get("z", 0),
                rotation=d.get("rotation", 0),
                svg=d.get("svg", ""),
            ).model_dump()
            for d in drawings
        ]

        return json.dumps(drawing_infos, indent=2)
    except Exception as e:
        return json.dumps(
            {"error": "Failed to list drawings", "project_id": project_id, "details": str(e)},
            indent=2,
        )


async def list_snapshots_impl(app: "IAppContext", project_id: str) -> str:
    """
    List all snapshots in a project

    Resource URI: projects://{project_id}/snapshots/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of snapshot information
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        # Get snapshots
        snapshots = await app.gns3.get_snapshots(project_id)

        # Build snapshot info
        from models import SnapshotInfo

        snapshot_infos = [
            SnapshotInfo(
                snapshot_id=s["snapshot_id"],
                name=s["name"],
                created_at=s.get("created_at", ""),
                project_id=project_id,
            ).model_dump()
            for s in snapshots
        ]

        return json.dumps(snapshot_infos, indent=2)
    except Exception as e:
        return json.dumps(
            {"error": "Failed to list snapshots", "project_id": project_id, "details": str(e)},
            indent=2,
        )


async def get_snapshot_impl(app: "IAppContext", project_id: str, snapshot_id: str) -> str:
    """
    Get snapshot details by ID

    Resource URI: projects://{project_id}/snapshots/{snapshot_id}

    Args:
        project_id: GNS3 project UUID
        snapshot_id: Snapshot UUID

    Returns:
        JSON object with snapshot details
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        # Get snapshots
        snapshots = await app.gns3.get_snapshots(project_id)
        snapshot = next((s for s in snapshots if s["snapshot_id"] == snapshot_id), None)

        if not snapshot:
            return json.dumps(
                {
                    "error": "Snapshot not found",
                    "project_id": project_id,
                    "snapshot_id": snapshot_id,
                },
                indent=2,
            )

        # Build snapshot info
        from models import SnapshotInfo

        snapshot_info = SnapshotInfo(
            snapshot_id=snapshot["snapshot_id"],
            name=snapshot["name"],
            created_at=snapshot.get("created_at", ""),
            project_id=project_id,
        )

        return json.dumps(snapshot_info.model_dump(), indent=2)
    except Exception as e:
        return json.dumps(
            {
                "error": "Failed to get snapshot",
                "project_id": project_id,
                "snapshot_id": snapshot_id,
                "details": str(e),
            },
            indent=2,
        )


async def get_project_readme_impl(app: "IAppContext", project_id: str):
    """Resource handler for projects://{id}/readme

    Returns project README/notes in markdown format
    """
    try:
        content = await app.gns3.get_project_readme(project_id)

        # If empty, provide default template
        if not content:
            content = "# Project Notes\n\n(No notes yet - use update_project_readme tool to add documentation)"

        return json.dumps(
            {"project_id": project_id, "content": content, "format": "markdown"}, indent=2
        )
    except Exception as e:
        return json.dumps(
            {"error": "Failed to get project README", "project_id": project_id, "details": str(e)},
            indent=2,
        )


async def get_topology_report_impl(app: "IAppContext", project_id: str):
    """Resource handler for projects://{id}/topology_report

    v0.40.0: Unified topology report with nodes, links, and statistics.

    Returns structured report showing:
    - Project information
    - Node statistics (types, statuses)
    - Link statistics
    - Table format for readability
    - JSON format for parsing

    Resource URI: projects://{project_id}/topology_report
    """
    try:
        import asyncio

        # Verify project exists and fetch all data concurrently
        projects_task = app.gns3.get_projects()
        nodes_task = app.gns3.get_nodes(project_id)
        links_task = app.gns3.get_links(project_id)

        projects, nodes, links = await asyncio.gather(projects_task, nodes_task, links_task)

        project = next((p for p in projects if p["project_id"] == project_id), None)

        if not project:
            return json.dumps({"error": "Project not found", "project_id": project_id}, indent=2)

        # Calculate statistics
        total_nodes = len(nodes)
        total_links = len(links)

        # Count nodes by status
        status_counts = {}
        for node in nodes:
            status = node.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count nodes by type
        type_counts = {}
        for node in nodes:
            node_type = node.get("node_type", "unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        # Build node connection map
        node_connections = {node["name"]: [] for node in nodes}
        node_lookup = {n["node_id"]: n for n in nodes}

        for link in links:
            nodes_data = link.get("nodes", [])
            if len(nodes_data) >= 2:
                node_a_id = nodes_data[0].get("node_id")
                node_b_id = nodes_data[1].get("node_id")

                node_a = node_lookup.get(node_a_id)
                node_b = node_lookup.get(node_b_id)

                if node_a and node_b:
                    # Get port info
                    port_a_num = nodes_data[0].get("port_number", 0)
                    port_b_num = nodes_data[1].get("port_number", 0)
                    adapter_a_num = nodes_data[0].get("adapter_number", 0)
                    adapter_b_num = nodes_data[1].get("adapter_number", 0)

                    # Find port names
                    port_a_name = f"eth{adapter_a_num}/{port_a_num}"
                    port_b_name = f"eth{adapter_b_num}/{port_b_num}"

                    if node_a.get("ports"):
                        for port in node_a["ports"]:
                            if (
                                port.get("adapter_number") == adapter_a_num
                                and port.get("port_number") == port_a_num
                            ):
                                port_a_name = port.get("name", port_a_name)
                                break

                    if node_b.get("ports"):
                        for port in node_b["ports"]:
                            if (
                                port.get("adapter_number") == adapter_b_num
                                and port.get("port_number") == port_b_num
                            ):
                                port_b_name = port.get("name", port_b_name)
                                break

                    # Add connection records
                    node_connections[node_a["name"]].append(
                        {"port": port_a_name, "dest_node": node_b["name"], "dest_port": port_b_name}
                    )
                    node_connections[node_b["name"]].append(
                        {"port": port_b_name, "dest_node": node_a["name"], "dest_port": port_a_name}
                    )

        # Build table output
        report_lines = []
        report_lines.append(f"TOPOLOGY REPORT - {project['name']}")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Statistics section
        report_lines.append(f"PROJECT: {project['name']}")
        report_lines.append(f"Status: {project.get('status', 'unknown')}")
        report_lines.append(f"Total Nodes: {total_nodes}")
        report_lines.append(f"Total Links: {total_links}")
        report_lines.append("")

        # Status breakdown
        if status_counts:
            report_lines.append("NODE STATUS:")
            for status, count in sorted(status_counts.items()):
                report_lines.append(f"  {status}: {count}")
            report_lines.append("")

        # Type breakdown
        if type_counts:
            report_lines.append("NODE TYPES:")
            for node_type, count in sorted(type_counts.items()):
                report_lines.append(f"  {node_type}: {count}")
            report_lines.append("")

        # Nodes table
        report_lines.append("NODES")
        report_lines.append("-" * 80)
        node_table_data = []
        for node in sorted(nodes, key=lambda n: n["name"]):
            conn_count = len(node_connections[node["name"]])
            node_table_data.append(
                [
                    node["name"],
                    node.get("node_type", "unknown"),
                    node.get("status", "unknown"),
                    f"{conn_count} links",
                ]
            )

        if node_table_data:
            report_lines.append(
                tabulate(
                    node_table_data,
                    headers=["Node Name", "Type", "Status", "Connections"],
                    tablefmt="simple",
                )
            )
        else:
            report_lines.append("No nodes in project")
        report_lines.append("")

        # Links table
        report_lines.append("LINKS")
        report_lines.append("-" * 80)
        link_table_data = []
        for link in links:
            nodes_data = link.get("nodes", [])
            if len(nodes_data) >= 2:
                node_a_id = nodes_data[0].get("node_id")
                node_b_id = nodes_data[1].get("node_id")
                node_a = node_lookup.get(node_a_id)
                node_b = node_lookup.get(node_b_id)

                if node_a and node_b:
                    port_a_num = nodes_data[0].get("port_number", 0)
                    port_b_num = nodes_data[1].get("port_number", 0)
                    adapter_a_num = nodes_data[0].get("adapter_number", 0)
                    adapter_b_num = nodes_data[1].get("adapter_number", 0)

                    port_a_name = f"eth{adapter_a_num}/{port_a_num}"
                    port_b_name = f"eth{adapter_b_num}/{port_b_num}"

                    link_table_data.append(
                        [node_a["name"], port_a_name, "→", node_b["name"], port_b_name]
                    )

        if link_table_data:
            report_lines.append(
                tabulate(
                    link_table_data,
                    headers=["Source", "Port", "", "Destination", "Port"],
                    tablefmt="simple",
                )
            )
        else:
            report_lines.append("No links in project")
        report_lines.append("")

        # Build JSON output
        json_data = {
            "project": {
                "name": project.get("name"),
                "project_id": project_id,
                "status": project.get("status"),
                "path": project.get("path"),
            },
            "statistics": {
                "total_nodes": total_nodes,
                "total_links": total_links,
                "status_breakdown": status_counts,
                "type_breakdown": type_counts,
            },
            "nodes": [
                {
                    "name": node["name"],
                    "node_id": node["node_id"],
                    "type": node.get("node_type"),
                    "status": node.get("status"),
                    "connections": node_connections[node["name"]],
                }
                for node in sorted(nodes, key=lambda n: n["name"])
            ],
            "links": [
                {
                    "link_id": link["link_id"],
                    "link_type": link.get("link_type", "ethernet"),
                    "source_node": (
                        node_lookup[link["nodes"][0]["node_id"]]["name"]
                        if len(link.get("nodes", [])) >= 1
                        and link["nodes"][0]["node_id"] in node_lookup
                        else "unknown"
                    ),
                    "dest_node": (
                        node_lookup[link["nodes"][1]["node_id"]]["name"]
                        if len(link.get("nodes", [])) >= 2
                        and link["nodes"][1]["node_id"] in node_lookup
                        else "unknown"
                    ),
                }
                for link in links
                if len(link.get("nodes", [])) >= 2
            ],
        }

        # Combine table and JSON
        table_output = "\n".join(report_lines)
        report_lines.append("JSON DATA:")
        report_lines.append("-" * 80)
        report_lines.append(json.dumps(json_data, indent=2))

        return "\n".join(report_lines)

    except Exception as e:
        return json.dumps(
            {
                "error": "Failed to generate topology report",
                "project_id": project_id,
                "details": str(e),
            },
            indent=2,
        )
