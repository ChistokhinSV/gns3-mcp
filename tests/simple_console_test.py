"""
Simple Direct Console Test

Tests telnet console connection without MCP layer.
Useful for debugging console issues.
"""

import argparse
import asyncio
import logging

import telnetlib3

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


async def test_console(host: str, port: int, duration: int = 10):
    """Test direct telnet connection to GNS3 console port"""

    logger.info(f"Connecting to {host}:{port}...")

    try:
        reader, writer = await telnetlib3.open_connection(host, port, encoding="utf-8")

        logger.info("Connected successfully")
        logger.info(f"Reading console output for {duration} seconds...")
        logger.info("-" * 60)

        # Read console output for specified duration
        end_time = asyncio.get_event_loop().time() + duration

        while asyncio.get_event_loop().time() < end_time:
            try:
                data = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                if data:
                    print(data, end="", flush=True)
            except asyncio.TimeoutError:
                pass

        logger.info("-" * 60)
        logger.info("Sending newline...")
        writer.write("\n")
        await writer.drain()

        # Read response
        await asyncio.sleep(1)
        data = await asyncio.wait_for(reader.read(4096), timeout=2.0)
        if data:
            logger.info("Response:")
            logger.info("-" * 60)
            print(data, end="", flush=True)
            logger.info("-" * 60)

        # Cleanup
        writer.close()
        await writer.wait_closed()
        logger.info("Connection closed")

    except Exception as e:
        logger.error(f"Connection failed: {e}")
        raise


async def main():
    parser = argparse.ArgumentParser(description="Test GNS3 console connection")
    parser.add_argument("--host", required=True, help="GNS3 server host")
    parser.add_argument("--port", type=int, required=True, help="Console port")
    parser.add_argument("--duration", type=int, default=10, help="Read duration (seconds)")

    args = parser.parse_args()

    try:
        await test_console(args.host, args.port, args.duration)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    asyncio.run(main())
