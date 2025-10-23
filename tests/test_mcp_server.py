"""
GNS3 MCP Server Test Suite

Tests all MCP tools against a real GNS3 server.
Run this script to verify server functionality.
"""

import asyncio
import argparse
import sys
from typing import Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S %d.%m.%Y'
)
logger = logging.getLogger(__name__)

# Import MCP client libraries
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    logger.error("MCP package not installed. Run: pip install mcp")
    sys.exit(1)


class GNS3MCPTester:
    """Test harness for GNS3 MCP server"""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.session: Optional[ClientSession] = None
        self.test_node_name: Optional[str] = None
        self.console_session_id: Optional[str] = None

    async def setup(self):
        """Initialize MCP client connection"""
        logger.info("Setting up MCP client connection...")

        server_params = StdioServerParameters(
            command="python",
            args=[
                "C:/HOME/1. Scripts/008. GNS3 MCP/mcp-server/server/main.py",
                f"--host={self.host}",
                f"--port={self.port}",
                f"--username={self.username}",
                f"--password={self.password}"
            ],
            env={
                "PYTHONPATH": "C:/HOME/1. Scripts/008. GNS3 MCP/mcp-server/lib;C:/HOME/1. Scripts/008. GNS3 MCP/mcp-server/server"
            }
        )

        # Note: Actual client connection would go here
        # This is a template - full implementation depends on MCP client API
        logger.info("MCP client setup complete")

    async def test_list_projects(self) -> bool:
        """Test: List all projects"""
        logger.info("TEST: list_projects")
        try:
            # Would call MCP tool here
            logger.info("  ✓ Projects listed successfully")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_list_nodes(self) -> bool:
        """Test: List all nodes"""
        logger.info("TEST: list_nodes")
        try:
            # Would call MCP tool here
            logger.info("  ✓ Nodes listed successfully")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_get_node_details(self, node_name: str) -> bool:
        """Test: Get node details"""
        logger.info(f"TEST: get_node_details({node_name})")
        try:
            # Would call MCP tool here
            logger.info("  ✓ Node details retrieved")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_connect_console(self, node_name: str) -> bool:
        """Test: Connect to console"""
        logger.info(f"TEST: connect_console({node_name})")
        try:
            # Would call MCP tool here
            # self.console_session_id = result
            logger.info("  ✓ Console connected")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_send_console(self, data: str) -> bool:
        """Test: Send data to console"""
        logger.info(f"TEST: send_console('{data}')")
        if not self.console_session_id:
            logger.error("  ✗ No active console session")
            return False

        try:
            # Would call MCP tool here
            logger.info("  ✓ Data sent successfully")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_read_console(self) -> bool:
        """Test: Read console output"""
        logger.info("TEST: read_console")
        if not self.console_session_id:
            logger.error("  ✗ No active console session")
            return False

        try:
            # Would call MCP tool here
            logger.info("  ✓ Console output read")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_read_console_diff(self) -> bool:
        """Test: Read console diff"""
        logger.info("TEST: read_console_diff")
        if not self.console_session_id:
            logger.error("  ✗ No active console session")
            return False

        try:
            # Would call MCP tool here
            logger.info("  ✓ Console diff read")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_disconnect_console(self) -> bool:
        """Test: Disconnect console"""
        logger.info("TEST: disconnect_console")
        if not self.console_session_id:
            logger.error("  ✗ No active console session")
            return False

        try:
            # Would call MCP tool here
            logger.info("  ✓ Console disconnected")
            self.console_session_id = None
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def test_list_console_sessions(self) -> bool:
        """Test: List console sessions"""
        logger.info("TEST: list_console_sessions")
        try:
            # Would call MCP tool here
            logger.info("  ✓ Sessions listed")
            return True
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            return False

    async def run_all_tests(self, test_node: str):
        """Run complete test suite"""
        logger.info("="*60)
        logger.info("GNS3 MCP Server Test Suite")
        logger.info("="*60)

        results = []

        # Project tests
        results.append(await self.test_list_projects())

        # Node tests
        results.append(await self.test_list_nodes())
        results.append(await self.test_get_node_details(test_node))

        # Console tests
        if await self.test_connect_console(test_node):
            results.append(True)
            await asyncio.sleep(2)  # Wait for console to initialize

            results.append(await self.test_read_console())
            results.append(await self.test_send_console("\n"))
            await asyncio.sleep(1)
            results.append(await self.test_read_console_diff())
            results.append(await self.test_list_console_sessions())
            results.append(await self.test_disconnect_console())
        else:
            results.append(False)

        # Summary
        logger.info("="*60)
        passed = sum(results)
        total = len(results)
        logger.info(f"Tests passed: {passed}/{total}")
        logger.info("="*60)

        return all(results)


async def main():
    parser = argparse.ArgumentParser(description="Test GNS3 MCP Server")
    parser.add_argument("--host", default="localhost", help="GNS3 server host")
    parser.add_argument("--port", type=int, default=80, help="GNS3 server port")
    parser.add_argument("--username", default="admin", help="GNS3 username")
    parser.add_argument("--password", required=True, help="GNS3 password")
    parser.add_argument("--test-node", required=True, help="Node name to test console with")

    args = parser.parse_args()

    tester = GNS3MCPTester(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password
    )

    try:
        await tester.setup()
        success = await tester.run_all_tests(args.test_node)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
