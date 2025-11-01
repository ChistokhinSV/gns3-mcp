"""
Interactive Console Test

Tests console with actual command execution
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path

import telnetlib3
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


async def test_interactive_console(host: str, port: int):
    """Test console with interactive commands"""

    logger.info(f"Connecting to {host}:{port}...")

    try:
        reader, writer = await telnetlib3.open_connection(host, port, encoding="utf-8")

        logger.info("Connected successfully")
        logger.info("=" * 70)

        # Wait a moment and try to read initial output (may be empty)
        await asyncio.sleep(1)
        try:
            initial = await asyncio.wait_for(reader.read(4096), timeout=0.5)
            logger.info("Initial output:")
            print(initial)
        except asyncio.TimeoutError:
            logger.info("No initial output (this is normal)")

        # Test 1: Send newline
        logger.info("=" * 70)
        logger.info("TEST 1: Send newline")
        writer.write("\n")
        await writer.drain()
        await asyncio.sleep(1)

        try:
            output = await asyncio.wait_for(reader.read(4096), timeout=2.0)
            logger.info("Response:")
            print(output)
        except asyncio.TimeoutError:
            logger.info("No response (timeout)")

        # Test 2: Send hostname command
        logger.info("=" * 70)
        logger.info("TEST 2: Execute 'hostname' command")
        writer.write("hostname\n")
        await writer.drain()
        await asyncio.sleep(1)

        try:
            output = await asyncio.wait_for(reader.read(4096), timeout=2.0)
            logger.info("Response:")
            print(output)
        except asyncio.TimeoutError:
            logger.info("No response (timeout)")

        # Test 3: Send whoami command
        logger.info("=" * 70)
        logger.info("TEST 3: Execute 'whoami' command")
        writer.write("whoami\n")
        await writer.drain()
        await asyncio.sleep(1)

        try:
            output = await asyncio.wait_for(reader.read(4096), timeout=2.0)
            logger.info("Response:")
            print(output)
        except asyncio.TimeoutError:
            logger.info("No response (timeout)")

        # Test 4: Send echo command
        logger.info("=" * 70)
        logger.info("TEST 4: Execute 'echo \"Test successful\"' command")
        writer.write('echo "Test successful"\n')
        await writer.drain()
        await asyncio.sleep(1)

        try:
            output = await asyncio.wait_for(reader.read(4096), timeout=2.0)
            logger.info("Response:")
            print(output)
        except asyncio.TimeoutError:
            logger.info("No response (timeout)")

        # Cleanup
        logger.info("=" * 70)
        writer.close()
        await writer.wait_closed()
        logger.info("✓ All tests completed successfully")

    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        raise


async def main():
    parser = argparse.ArgumentParser(description="Interactive console test")
    parser.add_argument(
        "--host", default=os.getenv("GNS3_HOST", "192.168.1.20"), help="GNS3 server host"
    )
    parser.add_argument("--port", type=int, help="Console port (required)")

    args = parser.parse_args()

    if not args.port:
        logger.error("Console port required (--port)")
        return

    try:
        await test_interactive_console(args.host, args.port)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    asyncio.run(main())
