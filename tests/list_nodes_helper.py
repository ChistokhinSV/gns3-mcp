"""
Quick helper to list GNS3 nodes and their console ports
"""

import asyncio
import httpx
import argparse
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def list_nodes(host: str, port: int, username: str, password: str):
    """List all nodes with console info"""

    base_url = f"http://{host}:{port}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Authenticate
        logger.info(f"Connecting to GNS3 at {base_url}...")
        auth_response = await client.post(
            f"{base_url}/v3/access/users/authenticate",
            json={"username": username, "password": password}
        )
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get projects
        projects_response = await client.get(f"{base_url}/v3/projects", headers=headers)
        projects = projects_response.json()

        # Find opened project
        opened = [p for p in projects if p["status"] == "opened"]
        if not opened:
            logger.error("No opened project found")
            return

        project = opened[0]
        project_id = project["project_id"]
        logger.info(f"\nProject: {project['name']}")
        logger.info("=" * 70)

        # Get nodes
        nodes_response = await client.get(
            f"{base_url}/v3/projects/{project_id}/nodes",
            headers=headers
        )
        nodes = nodes_response.json()

        # Display nodes
        logger.info(f"{'Name':<30} {'Status':<12} {'Console':<15} {'Type':<15}")
        logger.info("-" * 70)

        for node in nodes:
            name = node["name"]
            status = node["status"]
            console_type = node.get("console_type", "N/A")
            console_port = node.get("console", "N/A")

            console_info = f"{console_port} ({console_type})" if console_port != "N/A" else "N/A"

            logger.info(f"{name:<30} {status:<12} {console_info:<15}")

        logger.info("=" * 70)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("GNS3_HOST", "192.168.1.20"), help="GNS3 host")
    parser.add_argument("--port", type=int, default=int(os.getenv("GNS3_PORT", "80")), help="GNS3 port")
    parser.add_argument("--username", default=os.getenv("USER", "admin"), help="Username")
    parser.add_argument("--password", default=os.getenv("PASSWORD"), help="Password")

    args = parser.parse_args()

    if not args.password:
        logger.error("Password required (--password or PASSWORD env var)")
        return

    await list_nodes(args.host, args.port, args.username, args.password)


if __name__ == "__main__":
    asyncio.run(main())
