"""GNS3 MCP Server - Network lab automation with AI agent integration

Model Context Protocol (MCP) server for GNS3 network lab automation.
Control GNS3 projects, nodes, and device consoles through Claude Desktop or any MCP-compatible client.

Features:
- Project Management: Create, open, close GNS3 projects
- Node Control: Start/stop/restart nodes with wildcard patterns
- Console Access: Telnet console automation with pattern matching
- SSH Automation: Network device automation via Netmiko
- Network Topology: Batch connect/disconnect links, create drawings
- Docker Integration: Configure container networks, read/write files
"""

__version__ = "0.43.4"
__author__ = "Sergei Chistokhin"
__email__ = "Sergei@Chistokhin.com"
__license__ = "MIT"

__all__ = ["__version__"]
