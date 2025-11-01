"""
MCP Resources for GNS3 Server

Provides browsable state via MCP resource protocol.
Resources replace query tools for better IDE integration and discoverability.
"""

from .resource_manager import ResourceManager

__all__ = ["ResourceManager"]
