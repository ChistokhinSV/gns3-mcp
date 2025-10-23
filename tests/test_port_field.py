#!/usr/bin/env python3
"""Test script to verify port_number vs adapter_number field usage

This script tests the GNS3 v3 API link creation to confirm which field
is used for port specification.

Usage:
    python test_port_field.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir / 'mcp-server' / 'server'))
sys.path.insert(0, str(parent_dir / 'mcp-server' / 'lib'))

from dotenv import load_dotenv
from gns3_client import GNS3Client

# Load environment variables
load_dotenv(parent_dir / '.env')

# GNS3 connection details
GNS3_HOST = os.getenv('GNS3_HOST', 'localhost')
GNS3_PORT = int(os.getenv('GNS3_PORT', '80'))
GNS3_USER = os.getenv('GNS3_USER', 'admin')
GNS3_PASSWORD = os.getenv('GNS3_PASSWORD', '')


async def test_port_field():
    """Test port_number field in link creation"""
    print(f"[INFO] Connecting to GNS3 at {GNS3_HOST}:{GNS3_PORT}")

    async with GNS3Client(GNS3_HOST, GNS3_PORT, GNS3_USER, GNS3_PASSWORD) as client:
        # Authenticate
        if not await client.authenticate():
            print("[ERROR] Authentication failed")
            return False

        print("[OK] Authenticated successfully")

        # Get opened project
        projects = await client.get_projects()
        opened = [p for p in projects if p.get("status") == "opened"]

        if not opened:
            print("[ERROR] No opened project found")
            return False

        project = opened[0]
        project_id = project['project_id']
        print(f"[INFO] Using project: {project['name']}")

        # Get nodes
        nodes = await client.get_nodes(project_id)
        if len(nodes) < 2:
            print(f"[ERROR] Need at least 2 nodes in project, found {len(nodes)}")
            return False

        print(f"[INFO] Found {len(nodes)} nodes")

        # Get existing links
        links_before = await client.get_links(project_id)
        print(f"[INFO] Existing links: {len(links_before)}")

        # Analyze existing link structure
        if links_before:
            print("\n[INFO] Examining existing link structure...")
            sample_link = links_before[0]
            print(f"[INFO] Sample link keys: {list(sample_link.keys())}")
            if 'nodes' in sample_link:
                for i, node in enumerate(sample_link['nodes']):
                    print(f"[INFO] Node {i} keys: {list(node.keys())}")
                    print(f"[INFO] Node {i} values: {node}")

        # Select two nodes for testing - prefer switches or routers
        node_a = None
        node_b = None

        # Try to find Ethernet switches first (easiest to connect)
        switches = [n for n in nodes if n.get('node_type') == 'ethernet_switch']
        routers = [n for n in nodes if 'router' in n.get('node_type', '').lower()]

        if len(switches) >= 2:
            node_a = switches[0]
            node_b = switches[1]
            print(f"[INFO] Using switches for test")
        elif switches and routers:
            node_a = switches[0]
            node_b = routers[0]
            print(f"[INFO] Using switch and router for test")
        else:
            node_a = nodes[0]
            node_b = nodes[1]
            print(f"[INFO] Using first available nodes")

        print(f"[INFO] Test nodes: {node_a['name']} ({node_a['node_type']}) <-> "
              f"{node_b['name']} ({node_b['node_type']})")

        # Check which ports are in use
        used_ports_a = set()
        used_ports_b = set()

        for link in links_before:
            for node in link.get('nodes', []):
                if node.get('node_id') == node_a['node_id']:
                    used_ports_a.add(node.get('port_number', -1))
                if node.get('node_id') == node_b['node_id']:
                    used_ports_b.add(node.get('port_number', -1))

        # Find free ports (try 0-7)
        free_port_a = None
        free_port_b = None

        for port in range(8):
            if port not in used_ports_a and free_port_a is None:
                free_port_a = port
            if port not in used_ports_b and free_port_b is None:
                free_port_b = port

        if free_port_a is None or free_port_b is None:
            print(f"[ERROR] No free ports found on selected nodes")
            print(f"[INFO] Node A used ports: {used_ports_a}")
            print(f"[INFO] Node B used ports: {used_ports_b}")
            return False

        print(f"[INFO] Using free ports: {free_port_a} and {free_port_b}")

        # Test 1: Try with port_number
        print("\n[TEST 1] Creating link with port_number field...")
        link_spec_port_number = {
            "nodes": [
                {
                    "node_id": node_a["node_id"],
                    "adapter_number": 0,
                    "port_number": free_port_a
                },
                {
                    "node_id": node_b["node_id"],
                    "adapter_number": 0,
                    "port_number": free_port_b
                }
            ]
        }

        try:
            result = await client.create_link(project_id, link_spec_port_number)
            link_id = result.get('link_id')
            print(f"[OK] Link created successfully with port_number")
            print(f"[INFO] Link ID: {link_id}")
            print(f"[INFO] Link details: {result}")

            # Check the link structure
            if 'nodes' in result:
                for i, node in enumerate(result['nodes']):
                    print(f"[INFO] Node {i}: adapter={node.get('adapter_number')}, "
                          f"port={node.get('port_number')}")

            # Cleanup - delete the test link
            print(f"[INFO] Deleting test link {link_id}...")
            await client.delete_link(project_id, link_id)
            print("[OK] Test link deleted")

            return True

        except Exception as e:
            print(f"[FAIL] Failed to create link with port_number: {e}")

            # Test 2: Try alternate field name if port_number failed
            print("\n[TEST 2] Trying alternate field configuration...")
            return False

    return False


async def main():
    """Main test function"""
    print("=" * 60)
    print("GNS3 Port Field Test")
    print("=" * 60)
    print()

    try:
        success = await test_port_field()
        print()
        print("=" * 60)
        if success:
            print("[RESULT] port_number field VERIFIED - use in set_connection")
        else:
            print("[RESULT] port_number field FAILED - needs adjustment")
        print("=" * 60)
        return 0 if success else 1

    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
