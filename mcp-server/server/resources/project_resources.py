"""
Project-related MCP Resources

Handles resources for projects, nodes, links, templates, and drawings.
"""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import AppContext


async def list_projects_impl(app: "AppContext") -> str:
    """
    List all GNS3 projects

    Resource URI: gns3://projects/

    Returns:
        JSON array of projects with status information
    """
    try:
        projects = await app.gns3.get_projects()
        return json.dumps(projects, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list projects",
            "details": str(e)
        }, indent=2)


async def get_project_impl(app: "AppContext", project_id: str) -> str:
    """
    Get project details by ID

    Resource URI: gns3://projects/{project_id}

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON object with project details
    """
    try:
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == project_id), None)

        if not project:
            return json.dumps({
                "error": "Project not found",
                "project_id": project_id
            }, indent=2)

        return json.dumps(project, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get project",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


async def list_nodes_impl(app: "AppContext", project_id: str) -> str:
    """
    List all nodes in a project

    Resource URI: gns3://projects/{project_id}/nodes/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of node summaries
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == project_id), None)

        if not project:
            return json.dumps({
                "error": "Project not found",
                "project_id": project_id
            }, indent=2)

        # Get nodes
        nodes = await app.gns3.get_nodes(project_id)

        # Return lightweight NodeSummary format
        from models import NodeSummary
        summaries = [
            NodeSummary(
                node_id=n['node_id'],
                name=n['name'],
                node_type=n['node_type'],
                status=n['status'],
                console_type=n['console_type'],
                console=n.get('console')
            ).model_dump()
            for n in nodes
        ]

        return json.dumps(summaries, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list nodes",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


async def get_node_impl(app: "AppContext", project_id: str, node_id: str) -> str:
    """
    Get detailed node information

    Resource URI: gns3://projects/{project_id}/nodes/{node_id}

    Args:
        project_id: GNS3 project UUID
        node_id: Node UUID

    Returns:
        JSON object with complete node details (NodeInfo)
    """
    try:
        # Get all nodes
        nodes = await app.gns3.get_nodes(project_id)
        node = next((n for n in nodes if n['node_id'] == node_id), None)

        if not node:
            return json.dumps({
                "error": "Node not found",
                "project_id": project_id,
                "node_id": node_id
            }, indent=2)

        # Return full NodeInfo format
        from models import NodeInfo
        props = node.get('properties', {})
        info = NodeInfo(
            node_id=node['node_id'],
            name=node['name'],
            node_type=node['node_type'],
            status=node['status'],
            console_type=node['console_type'],
            console=node.get('console'),
            console_host=node.get('console_host'),
            compute_id=node.get('compute_id', 'local'),
            x=node.get('x', 0),
            y=node.get('y', 0),
            z=node.get('z', 0),
            locked=node.get('locked', False),
            ports=node.get('ports'),
            label=node.get('label'),
            symbol=node.get('symbol'),
            ram=props.get('ram'),
            cpus=props.get('cpus'),
            adapters=props.get('adapters'),
            hdd_disk_image=props.get('hdd_disk_image'),
            hda_disk_image=props.get('hda_disk_image')
        ).model_dump()

        return json.dumps(info, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get node",
            "project_id": project_id,
            "node_id": node_id,
            "details": str(e)
        }, indent=2)


async def list_links_impl(app: "AppContext", project_id: str) -> str:
    """
    List all network links in a project

    Resource URI: gns3://projects/{project_id}/links/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of link information with adapter/port details
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == project_id), None)

        if not project:
            return json.dumps({
                "error": "Project not found",
                "project_id": project_id
            }, indent=2)

        # Get links and nodes
        links = await app.gns3.get_links(project_id)
        nodes = await app.gns3.get_nodes(project_id)

        # Build node lookup
        node_lookup = {n['node_id']: n for n in nodes}

        # Build link info with port names
        from models import LinkInfo
        link_infos = []

        for link in links:
            nodes_data = link.get('nodes', [])
            if len(nodes_data) >= 2:
                node_a_id = nodes_data[0].get('node_id')
                node_b_id = nodes_data[1].get('node_id')
                node_a = node_lookup.get(node_a_id)
                node_b = node_lookup.get(node_b_id)

                if node_a and node_b:
                    # Get port names from node ports
                    port_a_num = nodes_data[0].get('port_number', 0)
                    port_b_num = nodes_data[1].get('port_number', 0)
                    adapter_a_num = nodes_data[0].get('adapter_number', 0)
                    adapter_b_num = nodes_data[1].get('adapter_number', 0)

                    port_a_name = None
                    port_b_name = None

                    if node_a.get('ports'):
                        for port in node_a['ports']:
                            if (port.get('adapter_number') == adapter_a_num and
                                port.get('port_number') == port_a_num):
                                port_a_name = port.get('name')
                                break

                    if node_b.get('ports'):
                        for port in node_b['ports']:
                            if (port.get('adapter_number') == adapter_b_num and
                                port.get('port_number') == port_b_num):
                                port_b_name = port.get('name')
                                break

                    # Build LinkEndpoint objects
                    from models import LinkEndpoint

                    endpoint_a = LinkEndpoint(
                        node_id=node_a_id,
                        node_name=node_a['name'],
                        adapter_number=adapter_a_num,
                        port_number=port_a_num,
                        port_name=port_a_name
                    )

                    endpoint_b = LinkEndpoint(
                        node_id=node_b_id,
                        node_name=node_b['name'],
                        adapter_number=adapter_b_num,
                        port_number=port_b_num,
                        port_name=port_b_name
                    )

                    link_info = LinkInfo(
                        link_id=link['link_id'],
                        link_type=link.get('link_type', 'ethernet'),
                        node_a=endpoint_a,
                        node_b=endpoint_b,
                        capturing=link.get('capturing', False),
                        capture_file_name=link.get('capture_file_name'),
                        capture_file_path=link.get('capture_file_path'),
                        capture_compute_id=link.get('capture_compute_id'),
                        suspend=link.get('suspend', False)
                    ).model_dump()

                    link_infos.append(link_info)

        return json.dumps(link_infos, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list links",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


async def list_templates_impl(app: "AppContext") -> str:
    """
    List available GNS3 templates

    Resource URI: gns3://templates

    Returns:
        JSON array of template information
    """
    try:
        templates = await app.gns3.get_templates()

        # Build template info (excludes usage to keep list lightweight)
        from models import TemplateInfo
        template_infos = [
            TemplateInfo(
                template_id=t['template_id'],
                name=t['name'],
                category=t.get('category', 'guest'),
                node_type=t.get('template_type'),
                builtin=t.get('builtin', False),
                compute_id=t.get('compute_id', 'local'),
                symbol=t.get('symbol')
                # usage excluded - use gns3://templates/{id} for full details
            ).model_dump()
            for t in templates
        ]

        return json.dumps(template_infos, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list templates",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


async def get_template_impl(app: "AppContext", template_id: str) -> str:
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
            template_id=template['template_id'],
            name=template['name'],
            category=template.get('category', 'guest'),
            node_type=template.get('template_type'),
            builtin=template.get('builtin', False),
            compute_id=template.get('compute_id', 'local'),
            symbol=template.get('symbol'),
            usage=template.get('usage', '')  # Includes credentials/setup instructions
        )

        return json.dumps(template_info.model_dump(), indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get template",
            "template_id": template_id,
            "details": str(e)
        }, indent=2)


async def get_node_template_usage_impl(app: "AppContext", project_id: str, node_id: str) -> str:
    """
    Get template usage notes for a specific node

    Resource URI: gns3://projects/{project_id}/nodes/{node_id}/template

    Args:
        project_id: GNS3 project UUID
        node_id: Node UUID

    Returns:
        JSON object with template details and usage notes for the node's template
    """
    try:
        nodes = await app.gns3.get_nodes(project_id)
        node = next((n for n in nodes if n['node_id'] == node_id), None)

        if not node:
            return json.dumps({
                "error": "Node not found",
                "project_id": project_id,
                "node_id": node_id
            }, indent=2)

        template_id = node.get('template_id')
        if not template_id:
            return json.dumps({
                "error": "Node has no associated template",
                "node_id": node_id,
                "node_name": node.get('name')
            }, indent=2)

        # Get template with usage
        template = await app.gns3.get_template(template_id)

        return json.dumps({
            "node_id": node_id,
            "node_name": node.get('name'),
            "template_id": template_id,
            "template_name": template['name'],
            "usage": template.get('usage', ''),
            "category": template.get('category'),
            "node_type": template.get('template_type')
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get node template usage",
            "project_id": project_id,
            "node_id": node_id,
            "details": str(e)
        }, indent=2)


async def list_drawings_impl(app: "AppContext", project_id: str) -> str:
    """
    List all drawing objects in a project

    Resource URI: gns3://projects/{project_id}/drawings/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of drawing information
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == project_id), None)

        if not project:
            return json.dumps({
                "error": "Project not found",
                "project_id": project_id
            }, indent=2)

        # Get drawings
        drawings = await app.gns3.get_drawings(project_id)

        # Build drawing info
        from models import DrawingInfo
        drawing_infos = [
            DrawingInfo(
                drawing_id=d['drawing_id'],
                x=d.get('x', 0),
                y=d.get('y', 0),
                z=d.get('z', 0),
                rotation=d.get('rotation', 0),
                svg=d.get('svg', '')
            ).model_dump()
            for d in drawings
        ]

        return json.dumps(drawing_infos, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list drawings",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


async def list_snapshots_impl(app: "AppContext", project_id: str) -> str:
    """
    List all snapshots in a project

    Resource URI: gns3://projects/{project_id}/snapshots/

    Args:
        project_id: GNS3 project UUID

    Returns:
        JSON array of snapshot information
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == project_id), None)

        if not project:
            return json.dumps({
                "error": "Project not found",
                "project_id": project_id
            }, indent=2)

        # Get snapshots
        snapshots = await app.gns3.get_snapshots(project_id)

        # Build snapshot info
        from models import SnapshotInfo
        snapshot_infos = [
            SnapshotInfo(
                snapshot_id=s['snapshot_id'],
                name=s['name'],
                created_at=s.get('created_at', ''),
                project_id=project_id
            ).model_dump()
            for s in snapshots
        ]

        return json.dumps(snapshot_infos, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to list snapshots",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)


async def get_snapshot_impl(app: "AppContext", project_id: str, snapshot_id: str) -> str:
    """
    Get snapshot details by ID

    Resource URI: gns3://projects/{project_id}/snapshots/{snapshot_id}

    Args:
        project_id: GNS3 project UUID
        snapshot_id: Snapshot UUID

    Returns:
        JSON object with snapshot details
    """
    try:
        # Verify project exists
        projects = await app.gns3.get_projects()
        project = next((p for p in projects if p['project_id'] == project_id), None)

        if not project:
            return json.dumps({
                "error": "Project not found",
                "project_id": project_id
            }, indent=2)

        # Get snapshots
        snapshots = await app.gns3.get_snapshots(project_id)
        snapshot = next((s for s in snapshots if s['snapshot_id'] == snapshot_id), None)

        if not snapshot:
            return json.dumps({
                "error": "Snapshot not found",
                "project_id": project_id,
                "snapshot_id": snapshot_id
            }, indent=2)

        # Build snapshot info
        from models import SnapshotInfo
        snapshot_info = SnapshotInfo(
            snapshot_id=snapshot['snapshot_id'],
            name=snapshot['name'],
            created_at=snapshot.get('created_at', ''),
            project_id=project_id
        )

        return json.dumps(snapshot_info.model_dump(), indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get snapshot",
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "details": str(e)
        }, indent=2)


async def get_project_readme_impl(app: "AppContext", project_id: str):
    """Resource handler for gns3://projects/{id}/readme

    Returns project README/notes in markdown format
    """
    try:
        content = await app.gns3.get_project_readme(project_id)

        # If empty, provide default template
        if not content:
            content = "# Project Notes\n\n(No notes yet - use update_project_readme tool to add documentation)"

        return json.dumps({
            "project_id": project_id,
            "content": content,
            "format": "markdown"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": "Failed to get project README",
            "project_id": project_id,
            "details": str(e)
        }, indent=2)
