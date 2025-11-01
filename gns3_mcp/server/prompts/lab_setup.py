"""Lab Setup Workflow Prompt

Guides users through creating complete lab topologies with automated node placement,
link configuration, and IP addressing.
"""

import math
from typing import Dict, List, Tuple

# ============================================================================
# Layout Algorithms - Calculate Node Positions
# ============================================================================


def calculate_star_layout(spoke_count: int) -> Dict[str, Tuple[int, int]]:
    """Calculate positions for star topology (hub-and-spoke)

    Args:
        spoke_count: Number of spoke devices

    Returns:
        Dict mapping device names to (x, y) coordinates
    """
    center_x, center_y = 960, 540  # Center of 1920x1080 workspace
    radius = 300  # Distance from hub to spokes

    positions = {"Hub": (center_x, center_y)}

    if spoke_count == 0:
        return positions

    angle_step = 360 / spoke_count
    for i in range(spoke_count):
        angle_rad = math.radians(i * angle_step)
        x = int(center_x + radius * math.cos(angle_rad))
        y = int(center_y + radius * math.sin(angle_rad))
        positions[f"Spoke{i + 1}"] = (x, y)

    return positions


def calculate_mesh_layout(device_count: int) -> Dict[str, Tuple[int, int]]:
    """Calculate positions for full mesh topology

    Arranges devices in a circle for clear visualization.

    Args:
        device_count: Number of devices

    Returns:
        Dict mapping device names to (x, y) coordinates
    """
    center_x, center_y = 960, 540
    radius = 350

    positions = {}

    if device_count == 0:
        return positions

    angle_step = 360 / device_count
    for i in range(device_count):
        angle_rad = math.radians(i * angle_step)
        x = int(center_x + radius * math.cos(angle_rad))
        y = int(center_y + radius * math.sin(angle_rad))
        positions[f"R{i + 1}"] = (x, y)

    return positions


def calculate_linear_layout(device_count: int) -> Dict[str, Tuple[int, int]]:
    """Calculate positions for linear topology (chain)

    Args:
        device_count: Number of devices

    Returns:
        Dict mapping device names to (x, y) coordinates
    """
    if device_count == 0:
        return {}

    start_x, y = 200, 540
    spacing = 350  # Horizontal spacing between devices

    positions = {}
    for i in range(device_count):
        x = start_x + (i * spacing)
        positions[f"R{i + 1}"] = (x, y)

    return positions


def calculate_ring_layout(device_count: int) -> Dict[str, Tuple[int, int]]:
    """Calculate positions for ring topology

    Args:
        device_count: Number of devices

    Returns:
        Dict mapping device names to (x, y) coordinates
    """
    return calculate_mesh_layout(device_count)  # Same visual layout


def calculate_ospf_layout(area_count: int, routers_per_area: int) -> Dict[str, Tuple[int, int]]:
    """Calculate positions for OSPF topology with backbone area

    Creates Area 0 (backbone) in center with other areas radiating outward.

    Args:
        area_count: Number of OSPF areas (including Area 0)
        routers_per_area: Routers per area

    Returns:
        Dict mapping device names to (x, y) coordinates
    """
    center_x, center_y = 960, 540
    positions = {}

    # Area 0 backbone routers in center
    if area_count > 0:
        backbone_radius = 150
        for i in range(routers_per_area):
            angle_rad = math.radians(i * (360 / routers_per_area))
            x = int(center_x + backbone_radius * math.cos(angle_rad))
            y = int(center_y + backbone_radius * math.sin(angle_rad))
            positions[f"ABR0-{i + 1}"] = (x, y)

    # Other areas radiating outward
    area_radius = 400
    for area_idx in range(1, area_count):
        area_angle_rad = math.radians(
            (area_idx - 1) * (360 / (area_count - 1 if area_count > 1 else 1))
        )
        area_center_x = int(center_x + area_radius * math.cos(area_angle_rad))
        area_center_y = int(center_y + area_radius * math.sin(area_angle_rad))

        # Routers within this area
        local_radius = 100
        for i in range(routers_per_area):
            angle_rad = math.radians(i * (360 / routers_per_area))
            x = int(area_center_x + local_radius * math.cos(angle_rad))
            y = int(area_center_y + local_radius * math.sin(angle_rad))
            positions[f"R{area_idx}-{i + 1}"] = (x, y)

    return positions


def calculate_bgp_layout(as_count: int) -> Dict[str, Tuple[int, int]]:
    """Calculate positions for BGP topology

    Creates multiple AS with edge routers.

    Args:
        as_count: Number of Autonomous Systems

    Returns:
        Dict mapping device names to (x, y) coordinates
    """
    center_x, center_y = 960, 540
    positions = {}

    if as_count == 0:
        return positions

    # Each AS gets 2 routers (iBGP pair)
    as_radius = 350
    local_radius = 120

    for as_idx in range(as_count):
        angle_rad = math.radians(as_idx * (360 / as_count))
        as_center_x = int(center_x + as_radius * math.cos(angle_rad))
        as_center_y = int(center_y + as_radius * math.sin(angle_rad))

        # Two routers per AS
        positions[f"AS{as_idx + 1}-R1"] = (int(as_center_x - local_radius / 2), as_center_y)
        positions[f"AS{as_idx + 1}-R2"] = (int(as_center_x + local_radius / 2), as_center_y)

    return positions


# ============================================================================
# Link Generation Functions
# ============================================================================


def generate_star_links(spoke_count: int) -> List[Tuple[str, str]]:
    """Generate links for star topology

    Args:
        spoke_count: Number of spoke devices

    Returns:
        List of (node_a, node_b) tuples
    """
    links = []
    for i in range(1, spoke_count + 1):
        links.append(("Hub", f"Spoke{i}"))
    return links


def generate_mesh_links(device_count: int) -> List[Tuple[str, str]]:
    """Generate links for full mesh topology

    Args:
        device_count: Number of devices

    Returns:
        List of (node_a, node_b) tuples
    """
    links = []
    for i in range(1, device_count + 1):
        for j in range(i + 1, device_count + 1):
            links.append((f"R{i}", f"R{j}"))
    return links


def generate_linear_links(device_count: int) -> List[Tuple[str, str]]:
    """Generate links for linear topology (chain)

    Args:
        device_count: Number of devices

    Returns:
        List of (node_a, node_b) tuples
    """
    links = []
    for i in range(1, device_count):
        links.append((f"R{i}", f"R{i + 1}"))
    return links


def generate_ring_links(device_count: int) -> List[Tuple[str, str]]:
    """Generate links for ring topology

    Args:
        device_count: Number of devices

    Returns:
        List of (node_a, node_b) tuples
    """
    links = generate_linear_links(device_count)
    if device_count > 2:
        links.append((f"R{device_count}", "R1"))  # Close the ring
    return links


def generate_ospf_links(area_count: int, routers_per_area: int) -> List[Tuple[str, str]]:
    """Generate links for OSPF topology

    Args:
        area_count: Number of OSPF areas
        routers_per_area: Routers per area

    Returns:
        List of (node_a, node_b) tuples
    """
    links = []

    # Full mesh within Area 0 backbone
    if area_count > 0:
        for i in range(routers_per_area):
            for j in range(i + 1, routers_per_area):
                links.append((f"ABR0-{i + 1}", f"ABR0-{j + 1}"))

    # Each non-backbone area
    for area_idx in range(1, area_count):
        # Ring within area
        for i in range(routers_per_area):
            next_i = (i + 1) % routers_per_area
            links.append((f"R{area_idx}-{i + 1}", f"R{area_idx}-{next_i + 1}"))

        # Connect to backbone (first router in area connects to first ABR)
        if routers_per_area > 0:
            links.append(("ABR0-1", f"R{area_idx}-1"))

    return links


def generate_bgp_links(as_count: int) -> List[Tuple[str, str]]:
    """Generate links for BGP topology

    Args:
        as_count: Number of Autonomous Systems

    Returns:
        List of (node_a, node_b) tuples
    """
    links = []

    # iBGP within each AS
    for as_idx in range(1, as_count + 1):
        links.append((f"AS{as_idx}-R1", f"AS{as_idx}-R2"))

    # eBGP between adjacent AS
    for as_idx in range(1, as_count):
        links.append((f"AS{as_idx}-R2", f"AS{as_idx + 1}-R1"))

    # Close the circle for > 2 AS
    if as_count > 2:
        links.append((f"AS{as_count}-R2", "AS1-R1"))

    return links


# ============================================================================
# IP Addressing Schemes
# ============================================================================


def generate_star_ips(spoke_count: int) -> Dict[str, Dict[str, str]]:
    """Generate IP addresses for star topology

    Args:
        spoke_count: Number of spoke devices

    Returns:
        Dict mapping node names to interface IP configs
    """
    ips = {}
    base = "10.0"

    # Hub gets .1 on each spoke subnet
    hub_ips = {}
    for i in range(1, spoke_count + 1):
        hub_ips[f"Gi0/{i - 1}"] = f"{base}.{i}.1/24"
    ips["Hub"] = hub_ips

    # Each spoke gets .2 on its subnet
    for i in range(1, spoke_count + 1):
        ips[f"Spoke{i}"] = {"Gi0/0": f"{base}.{i}.2/24"}

    return ips


def generate_mesh_ips(device_count: int) -> Dict[str, Dict[str, str]]:
    """Generate IP addresses for mesh topology (point-to-point links)

    Args:
        device_count: Number of devices

    Returns:
        Dict mapping node names to interface IP configs
    """
    ips = {f"R{i}": {} for i in range(1, device_count + 1)}

    subnet = 1
    interface_counters = {f"R{i}": 0 for i in range(1, device_count + 1)}

    for i in range(1, device_count + 1):
        for j in range(i + 1, device_count + 1):
            # R{i} gets .1, R{j} gets .2 on subnet
            ips[f"R{i}"][f"Gi0/{interface_counters[f'R{i}']}"] = f"10.0.{subnet}.1/30"
            ips[f"R{j}"][f"Gi0/{interface_counters[f'R{j}']}"] = f"10.0.{subnet}.2/30"

            interface_counters[f"R{i}"] += 1
            interface_counters[f"R{j}"] += 1
            subnet += 1

    return ips


def generate_linear_ips(device_count: int) -> Dict[str, Dict[str, str]]:
    """Generate IP addresses for linear topology

    Args:
        device_count: Number of devices

    Returns:
        Dict mapping node names to interface IP configs
    """
    ips = {f"R{i}": {} for i in range(1, device_count + 1)}

    for i in range(1, device_count):
        # Link between R{i} and R{i+1}
        ips[f"R{i}"]["Gi0/1"] = f"10.0.{i}.1/30"
        ips[f"R{i + 1}"]["Gi0/0"] = f"10.0.{i}.2/30"

    return ips


def generate_ospf_ips(area_count: int, routers_per_area: int) -> Dict[str, Dict[str, str]]:
    """Generate IP addresses for OSPF topology

    Args:
        area_count: Number of OSPF areas
        routers_per_area: Routers per area

    Returns:
        Dict mapping node names to interface IP configs
    """
    ips = {}
    subnet = 1

    # Area 0 backbone - 10.0.x.x range
    for i in range(routers_per_area):
        ips[f"ABR0-{i + 1}"] = {"Loopback0": f"10.0.0.{i + 1}/32"}
        # Interfaces will be added when creating mesh links

    # Other areas - 10.{area}.x.x range
    for area_idx in range(1, area_count):
        for i in range(routers_per_area):
            ips[f"R{area_idx}-{i + 1}"] = {"Loopback0": f"10.{area_idx}.0.{i + 1}/32"}

    return ips


def generate_bgp_ips(as_count: int) -> Dict[str, Dict[str, str]]:
    """Generate IP addresses for BGP topology

    Args:
        as_count: Number of Autonomous Systems

    Returns:
        Dict mapping node names to interface IP configs
    """
    ips = {}

    for as_idx in range(1, as_count + 1):
        # iBGP link within AS
        ips[f"AS{as_idx}-R1"] = {
            "Loopback0": f"192.168.{as_idx}.1/32",
            "Gi0/0": f"10.{as_idx}.1.1/30",  # iBGP link
        }
        ips[f"AS{as_idx}-R2"] = {
            "Loopback0": f"192.168.{as_idx}.2/32",
            "Gi0/0": f"10.{as_idx}.1.2/30",  # iBGP link
        }

    # eBGP links use 172.16.x.x range
    ebgp_subnet = 1
    for as_idx in range(1, as_count):
        ips[f"AS{as_idx}-R2"]["Gi0/1"] = f"172.16.{ebgp_subnet}.1/30"
        ips[f"AS{as_idx + 1}-R1"]["Gi0/1"] = f"172.16.{ebgp_subnet}.2/30"
        ebgp_subnet += 1

    # Close the circle
    if as_count > 2:
        ips[f"AS{as_count}-R2"]["Gi0/1"] = f"172.16.{ebgp_subnet}.1/30"
        ips["AS1-R1"]["Gi0/1"] = f"172.16.{ebgp_subnet}.2/30"

    return ips


# ============================================================================
# Main Prompt Generator
# ============================================================================


def render_lab_setup_prompt(
    topology_type: str,
    device_count: int,
    template_name: str = "Alpine Linux",
    project_name: str = "Lab Topology",
) -> str:
    """Generate lab setup workflow prompt

    Args:
        topology_type: Type of topology (star, mesh, linear, ring, ospf, bgp)
        device_count: Number of devices (or spokes for star, areas for OSPF, AS for BGP)
        template_name: GNS3 template to use for nodes
        project_name: Name for the new project

    Returns:
        Formatted workflow prompt
    """

    # Calculate layout based on topology type
    if topology_type == "star":
        positions = calculate_star_layout(device_count)
        links = generate_star_links(device_count)
        ips = generate_star_ips(device_count)
        total_devices = device_count + 1  # spokes + hub
        topology_desc = f"Star topology with 1 hub and {device_count} spokes"
    elif topology_type == "mesh":
        positions = calculate_mesh_layout(device_count)
        links = generate_mesh_links(device_count)
        ips = generate_mesh_ips(device_count)
        total_devices = device_count
        topology_desc = f"Full mesh topology with {device_count} routers"
    elif topology_type == "linear":
        positions = calculate_linear_layout(device_count)
        links = generate_linear_links(device_count)
        ips = generate_linear_ips(device_count)
        total_devices = device_count
        topology_desc = f"Linear topology with {device_count} routers in a chain"
    elif topology_type == "ring":
        positions = calculate_ring_layout(device_count)
        links = generate_ring_links(device_count)
        ips = generate_mesh_ips(device_count)  # Use mesh IPs for simplicity
        total_devices = device_count
        topology_desc = f"Ring topology with {device_count} routers"
    elif topology_type == "ospf":
        # device_count represents number of areas
        routers_per_area = 3
        positions = calculate_ospf_layout(device_count, routers_per_area)
        links = generate_ospf_links(device_count, routers_per_area)
        ips = generate_ospf_ips(device_count, routers_per_area)
        total_devices = device_count * routers_per_area
        topology_desc = (
            f"OSPF topology with {device_count} areas, {routers_per_area} routers per area"
        )
    elif topology_type == "bgp":
        # device_count represents number of AS
        positions = calculate_bgp_layout(device_count)
        links = generate_bgp_links(device_count)
        ips = generate_bgp_ips(device_count)
        total_devices = device_count * 2  # 2 routers per AS
        topology_desc = f"BGP topology with {device_count} Autonomous Systems"
    else:
        return f"Error: Unknown topology type '{topology_type}'. Supported: star, mesh, linear, ring, ospf, bgp"

    # Generate node creation commands
    node_commands = []
    for node_name, (x, y) in positions.items():
        node_commands.append(f'create_node("{template_name}", {x}, {y}, node_name="{node_name}")')

    # Generate link creation commands
    link_commands = []
    for node_a, node_b in links:
        link_commands.append(
            f"""set_connection([
    {{"action": "connect", "node_a": "{node_a}", "node_b": "{node_b}", "adapter_a": 0, "adapter_b": 0, "port_a": 0, "port_b": 0}}
])"""
        )

    # Generate IP configuration examples
    ip_examples = []
    for node_name, interfaces in list(ips.items())[:3]:  # Show first 3 nodes
        ip_examples.append(f"\n**{node_name}:**")
        for interface, ip_addr in interfaces.items():
            ip_examples.append(f"- {interface}: {ip_addr}")

    if len(ips) > 3:
        ip_examples.append(f"\n*(... {len(ips) - 3} more nodes)*")

    workflow = f"""# Lab Setup: {topology_desc}

This workflow automates creation of a complete {topology_type} lab topology.

## What Will Be Created

- **Project**: {project_name}
- **Topology**: {topology_desc}
- **Total Devices**: {total_devices}
- **Total Links**: {len(links)}
- **Template**: {template_name}

## Prerequisites

- GNS3 server running and authenticated
- Template "{template_name}" available (check with resource `projects://{{id}}/templates/`)
- Sufficient system resources for {total_devices} nodes

## Step 1: Create Project

Create a new project for this lab:

```
create_project("{project_name}")
```

This will create and auto-open the project.

## Step 2: Create Nodes

Create all {total_devices} nodes with calculated positions:

```python
# Create nodes (copy all commands together)
{chr(10).join(node_commands)}
```

**Layout**: Nodes are positioned using {topology_type} layout algorithm for optimal visualization.

## Step 3: Create Links

Connect nodes according to {topology_type} topology:

```python
# Create links (copy all commands together)
{chr(10).join(link_commands)}
```

## Step 4: Configure IP Addressing (Optional)

Suggested IP addressing scheme:
{chr(10).join(ip_examples)}

Use SSH or console tools to configure IP addresses on each node's interfaces.

## Step 5: Start Nodes

Start all nodes in the project:

```python
# Get all nodes and start them
# (Use resource projects://{{id}}/nodes/ to list, then set_node() to start each)
```

## Step 6: Verify Topology

Check the topology visually:

```python
export_topology_diagram("C:/DOWNLOAD_TEMP/{project_name.replace(" ", "_")}", format="both")
```

This creates SVG and PNG diagrams of your topology.

## Step 7: Document in Project README

**IMPORTANT**: Document the lab topology in the project README for future reference and team collaboration:

```python
update_project_readme(f\"\"\"
# {project_name}

## Topology Overview
- **Type**: {topology_type.capitalize()}
- **Device Count**: {device_count}
- **Template**: {template_name}
- **Created**: {{current_date}}

## Network Design

### IP Addressing Scheme
[Document your IP ranges, subnets, management IPs]

Example:
- Management subnet: 192.168.1.0/24
- Node IPs: 192.168.1.10 - 192.168.1.{10 + device_count}

### Node List
| Node Name | IP Address | Credentials | Notes |
|-----------|------------|-------------|-------|
| [Fill in from your nodes] | | | |

### Links and Connectivity
[Document physical connections between nodes]

Example:
- Node1 Gi0/0 ← → Node2 Gi0/0
- Node2 Gi0/1 ← → Node3 Gi0/0

## Configuration Notes

### Routing Protocol
[If using OSPF/BGP, document areas, AS numbers, network statements]

### Known Issues
[Document any limitations or known problems]

### Troubleshooting Tips
[Document common issues and solutions]

## Access Information

### Console Access
- Use `sessions://console/` resource to view active console sessions
- All nodes use telnet console type

### SSH Access
[Document after configuring SSH on nodes]

## References
- Topology diagram: [Path to SVG/PNG files]
- Configuration backups: [If you create backups]
\"\"\")
```

**Benefits of README Documentation:**
- Quick reference for node IPs and credentials
- Helps troubleshooting by documenting expected behavior
- Facilitates team collaboration and handoffs
- Records configuration decisions and rationale
- Tracks known issues and solutions

## Topology-Specific Notes

"""

    # Add topology-specific guidance
    if topology_type == "star":
        workflow += """**Star Topology:**
- Hub is central connection point
- All traffic between spokes goes through hub
- Good for: Centralized services, hub-and-spoke networks
- Consider: Hub is single point of failure
"""
    elif topology_type == "mesh":
        workflow += f"""**Full Mesh Topology:**
- Every router connects to every other router
- Total links: {len(links)} (n*(n-1)/2 where n={device_count})
- Good for: Redundancy, multiple paths
- Consider: Complexity grows quickly (use for ≤5 devices)
"""
    elif topology_type == "linear":
        workflow += """**Linear Topology:**
- Routers connected in a chain
- Simple serial path
- Good for: WAN simulations, basic routing practice
- Consider: End devices have only one path
"""
    elif topology_type == "ring":
        workflow += """**Ring Topology:**
- Each router connects to exactly two neighbors
- Forms a closed loop
- Good for: Redundancy with minimal links, loop-free protocols
- Consider: Requires spanning tree or similar protocol
"""
    elif topology_type == "ospf":
        workflow += f"""**OSPF Multi-Area Topology:**
- Area 0 (backbone) with {routers_per_area} ABRs in center
- {device_count - 1} additional areas radiating outward
- ABRs connect areas to backbone
- Good for: OSPF learning, hierarchical routing
- Configure: OSPF process, area assignments, network statements
"""
    elif topology_type == "bgp":
        workflow += f"""**BGP Topology:**
- {device_count} Autonomous Systems
- 2 routers per AS (iBGP peering)
- eBGP between adjacent AS
- Good for: BGP learning, AS path manipulation
- Configure: BGP process, AS numbers, neighbor statements
"""

    workflow += """
## Next Steps

1. **Configure routing**: Use SSH or console to configure routing protocols
2. **Test connectivity**: Verify reachability between nodes
3. **Create snapshot**: Save working configuration with `create_snapshot()`
4. **Document**: Add labels and drawings to clarify topology

## Troubleshooting

**Nodes not starting:**
- Check system resources (RAM, CPU)
- Verify template is compatible
- Check GNS3 server logs

**Links not connecting:**
- Ensure nodes are created before creating links
- Verify node names match exactly
- Check adapter/port numbers are valid for template

**Topology looks wrong:**
- Export diagram to verify layout
- Manually adjust node positions with `set_node()` if needed
- Positions can be fine-tuned: `set_node("NodeName", x=100, y=200)`

## Cleanup

To start over:
```python
close_project()
# Then delete project from GNS3 GUI if needed
```
"""

    return workflow
