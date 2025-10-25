"""Topology Discovery Workflow Prompt

Guides users through discovering and visualizing network topology using MCP resources and tools.
"""


async def render_topology_discovery_prompt(
    project_name: str = None,
    include_export: bool = True
) -> str:
    """Generate topology discovery workflow prompt

    Args:
        project_name: Optional project name to focus on (default: guide user to select)
        include_export: Include export/visualization steps (default: True)

    Returns:
        Formatted workflow instructions as string
    """

    project_section = f"**Project: {project_name}**" if project_name else """
## Step 1: Select Project

List available projects to find the one you want to explore:

**Using MCP Resources (recommended):**
```
# Browse all projects
Resource: gns3://projects/

# View specific project details
Resource: gns3://projects/{{project_id}}
```

**Using Tools:**
```
list_projects()
```

Identify the project ID for the topology you want to discover.
"""

    workflow = f"""# Topology Discovery Workflow

This guided workflow helps you discover and visualize network topology in GNS3 projects.

{project_section}

## Step 2: Discover Nodes

Explore all network devices and hosts in the project:

**Using MCP Resources (recommended):**
```
# List all nodes with basic info
Resource: gns3://projects/{{project_id}}/nodes/

# Get detailed node information
Resource: gns3://projects/{{project_id}}/nodes/{{node_id}}
```

**Node Information Includes:**
- Node name and type (router, switch, host, etc.)
- Status (started, stopped, suspended)
- Console type and port (for device access)
- Icon and position (for visualization)
- Ports and adapters (for connectivity)

**Key Observations:**
- Note node types: routers, switches, hosts, clouds, NAT
- Check node status: which devices are running?
- Identify console types: telnet, VNC, none
- Review port counts: how many interfaces?

## Step 3: Discover Links

Map all network connections between devices:

**Using MCP Resources (recommended):**
```
# List all links with connection details
Resource: gns3://projects/{{project_id}}/links/
```

**Link Information Includes:**
- Link ID and type (ethernet, serial, etc.)
- Connected nodes (node_a, node_b)
- Port mappings (adapter/port on each side)
- Port names (e.g., "GigabitEthernet0/0", "eth0")
- Link status (active, suspended)

**Understanding Connectivity:**
- Each link connects two nodes via specific ports
- Adapter numbers map to interface slots (0 = first slot)
- Port numbers map to ports within that slot
- Port names provide human-readable labels

**Example Link Analysis:**
```
Link: R1 (GigabitEthernet0/0) ↔ SW1 (Ethernet0)
- R1: adapter 0, port 0 → "GigabitEthernet0/0"
- SW1: adapter 0, port 0 → "Ethernet0"
- Status: active (green indicator)
```

## Step 4: Discover Templates

View available device templates for understanding device capabilities:

**Using MCP Resources:**
```
Resource: gns3://projects/{{project_id}}/templates/
```

**Template Information:**
- Device types available in this GNS3 installation
- Default configurations and capabilities
- Icon assignments

## Step 5: Discover Drawings

Explore visual annotations in the topology:

**Using MCP Resources:**
```
Resource: gns3://projects/{{project_id}}/drawings/
```

**Drawing Types:**
- Rectangles: Containers or zones
- Ellipses: Circular regions
- Lines: Visual connections or boundaries
- Text: Labels and annotations

**Purpose:** Drawings help organize and document topology structure (e.g., "DMZ", "Internal Network", "Cloud Region").
"""

    if include_export:
        workflow += """
## Step 6: Visualize Topology

Export the topology as a visual diagram:

**Using export_topology_diagram Tool:**

**Basic Export (SVG):**
```
export_topology_diagram(
    output_path="C:/path/to/output",
    format="svg"
)
```

**High-Quality Export (PNG, 300 DPI):**
```
export_topology_diagram(
    output_path="C:/path/to/output",
    format="png",
    dpi=300
)
```

**Both Formats:**
```
export_topology_diagram(
    output_path="C:/path/to/output",
    format="both"
)
```

**Custom Crop Region:**
```
export_topology_diagram(
    output_path="C:/path/to/output",
    format="both",
    crop_region={
        "x": 100,
        "y": 100,
        "width": 1000,
        "height": 800
    }
)
```

**Diagram Features:**
- Nodes rendered with icons and labels
- Links with port status indicators:
  - 🟢 Green = active (node started, link not suspended)
  - 🔴 Red = stopped (node stopped or link suspended)
- Drawings for visual organization
- Auto-fitting to content with padding
- High-DPI support for presentations

## Step 7: Analyze Topology Structure

**Common Topology Patterns:**

**Hub-and-Spoke:**
- Central router/switch (hub)
- Multiple edge devices (spokes)
- Example: Branch office connecting to HQ

**Full Mesh:**
- Each device connects to every other device
- High redundancy, high cost
- Example: Data center core layer

**Partial Mesh:**
- Some devices interconnected
- Balance between redundancy and cost
- Example: Regional office connectivity

**Tiered (Hierarchical):**
- Access layer (end devices)
- Distribution layer (aggregation)
- Core layer (high-speed backbone)
- Example: Campus network

**Questions to Answer:**
1. What is the topology pattern? (hub-and-spoke, mesh, tiered, etc.)
2. Which devices are critical path? (single point of failure?)
3. Are there redundant paths? (backup routes?)
4. What are the device roles? (edge, core, access, etc.)
5. How are zones separated? (VLANs, subnets, physical segments?)
"""

    workflow += """
## Troubleshooting Discovery Issues

**Project Not Found:**
- Verify project name is correct
- Check if project is open (use open_project tool)
- List all projects to confirm existence

**No Nodes Returned:**
- Confirm project is open
- Check if project has any devices added
- Verify project ID is correct

**Missing Link Information:**
- Ensure nodes are connected in GNS3 GUI
- Check if links are suspended (show as red)
- Verify adapter/port numbers are valid

**Export Fails:**
- Check output path exists and is writable
- Verify sufficient disk space
- Try SVG format first (smaller, faster)

## Next Steps

Once you've discovered the topology:

1. **Document findings**: Note device roles, connectivity patterns, redundancy
2. **Identify gaps**: Missing links, incomplete redundancy, bottlenecks
3. **Plan changes**: Decide what modifications are needed
4. **Access devices**: Use console or SSH tools to configure devices
5. **Test connectivity**: Verify network paths work as designed

## Related Resources and Tools

**MCP Resources (browsing state):**
- `gns3://projects/` - List all projects
- `gns3://projects/{id}` - Project details
- `gns3://projects/{id}/nodes/` - All nodes
- `gns3://projects/{id}/nodes/{id}` - Specific node details
- `gns3://projects/{id}/links/` - All links
- `gns3://projects/{id}/templates/` - Available templates
- `gns3://projects/{id}/drawings/` - Visual annotations

**Tools (actions):**
- `open_project(name)` - Open a project
- `set_node(...)` - Modify node properties or control state
- `set_connection(...)` - Manage links between nodes
- `console_send(node, data)` - Access device console
- `ssh_configure(node, device_dict)` - Establish SSH session
- `export_topology_diagram(...)` - Create visual diagram

**Typical Workflow After Discovery:**
1. Discovery (this workflow)
2. SSH Setup (if automating devices) → Use "SSH Setup Workflow" prompt
3. Configuration Changes → Use appropriate tools
4. Troubleshooting (if issues occur) → Use "Troubleshooting Workflow" prompt
"""

    return workflow
