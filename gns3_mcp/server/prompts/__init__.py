"""
MCP Prompts for GNS3 Server

Provides guided workflows via MCP prompt protocol.
"""

from .lab_setup import render_lab_setup_prompt
from .node_setup import render_node_setup_prompt
from .ssh_setup import render_ssh_setup_prompt
from .topology_discovery import render_topology_discovery_prompt
from .troubleshooting import render_troubleshooting_prompt

__all__ = [
    "render_ssh_setup_prompt",
    "render_topology_discovery_prompt",
    "render_troubleshooting_prompt",
    "render_lab_setup_prompt",
    "render_node_setup_prompt",
]
