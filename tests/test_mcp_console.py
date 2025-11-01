"""
Test MCP Console Operations

Tests console functionality through the MCP server's console_manager
"""

import asyncio
import os
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-server" / "server"))

import logging

from console_manager import ConsoleManager
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S %d.%m.%Y"
)
logger = logging.getLogger(__name__)


async def test_console_manager(host: str, port: int, node_name: str):
    """Test ConsoleManager functionality"""

    manager = ConsoleManager()

    logger.info("=" * 70)
    logger.info(f"Testing ConsoleManager with {node_name}")
    logger.info("=" * 70)

    try:
        # Test 1: Connect
        logger.info("\nTEST 1: Connect to console")
        session_id = await manager.connect(host, port, node_name)
        logger.info(f"✓ Connected: session_id = {session_id}")

        # Wait for console to initialize
        await asyncio.sleep(2)

        # Test 2: Read initial output
        logger.info("\nTEST 2: Read console output")
        output = manager.get_output(session_id)
        if output:
            logger.info(f"✓ Read {len(output)} bytes")
            logger.info("Output preview:")
            print("-" * 70)
            print(output[-200:] if len(output) > 200 else output)  # Last 200 chars
            print("-" * 70)
        else:
            logger.warning("⚠ No output yet (buffer may be empty)")

        # Test 3: Send command
        logger.info("\nTEST 3: Send newline")
        success = await manager.send(session_id, "\n")
        if success:
            logger.info("✓ Sent successfully")
        else:
            logger.error("✗ Send failed")
            return False

        await asyncio.sleep(1)

        # Test 4: Read diff
        logger.info("\nTEST 4: Read console diff")
        diff = manager.get_diff(session_id)
        if diff:
            logger.info(f"✓ Read {len(diff)} bytes of new data")
            logger.info("Diff content:")
            print("-" * 70)
            print(diff)
            print("-" * 70)
        else:
            logger.info("No new data (this may be normal)")

        # Test 5: Send hostname command
        logger.info("\nTEST 5: Send 'hostname' command")
        success = await manager.send(session_id, "hostname\n")
        if success:
            logger.info("✓ Sent successfully")
        else:
            logger.error("✗ Send failed")
            return False

        await asyncio.sleep(1)

        # Test 6: Read response
        logger.info("\nTEST 6: Read response")
        diff = manager.get_diff(session_id)
        if diff:
            logger.info(f"✓ Read {len(diff)} bytes")
            logger.info("Response:")
            print("-" * 70)
            print(diff)
            print("-" * 70)
        else:
            logger.warning("⚠ No response")

        # Test 7: List sessions
        logger.info("\nTEST 7: List active sessions")
        sessions = manager.list_sessions()
        logger.info(f"✓ Found {len(sessions)} active session(s)")
        for sid, info in sessions.items():
            logger.info(f"  - {info['node_name']}: {info['buffer_size']} bytes buffered")

        # Test 8: Disconnect
        logger.info("\nTEST 8: Disconnect console")
        success = await manager.disconnect(session_id)
        if success:
            logger.info("✓ Disconnected successfully")
        else:
            logger.error("✗ Disconnect failed")
            return False

        logger.info("\n" + "=" * 70)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("GNS3_HOST", "192.168.1.20"))
    parser.add_argument("--port", type=int, required=True, help="Console port")
    parser.add_argument("--node-name", default="AlpineLinuxTest-1", help="Node name")

    args = parser.parse_args()

    success = await test_console_manager(args.host, args.port, args.node_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
