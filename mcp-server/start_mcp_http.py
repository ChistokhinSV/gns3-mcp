"""
GNS3 MCP Server - HTTP Transport Mode

Starts the MCP server with HTTP transport for Windows service deployment.
Loads configuration from .env file and sets up proper logging.

Usage:
    python start_mcp_http.py

Environment variables (.env):
    USER - GNS3 username
    PASSWORD - GNS3 password
    GNS3_HOST - GNS3 server hostname/IP (default: 192.168.1.20)
    GNS3_PORT - GNS3 server port (default: 80)
    HTTP_HOST - HTTP server bind address (default: 127.0.0.1)
    HTTP_PORT - HTTP server port (default: 8100)
    LOG_LEVEL - Logging level (default: INFO)
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add server modules to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / "lib"))
sys.path.insert(0, str(script_dir / "server"))

# Load environment variables
from dotenv import load_dotenv
env_path = script_dir.parent / ".env"
load_dotenv(env_path)

# Configure logging with timestamp format
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    datefmt="%H:%M:%S %d.%m.%Y",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(script_dir.parent / "mcp-http-server.log")
    ]
)

logger = logging.getLogger("gns3-mcp-http")

# Get configuration from environment
http_host = os.getenv("HTTP_HOST", "127.0.0.1")
http_port = int(os.getenv("HTTP_PORT", "8100"))
gns3_host = os.getenv("GNS3_HOST", "192.168.1.20")
gns3_port = int(os.getenv("GNS3_PORT", "80"))
username = os.getenv("USER")
password = os.getenv("PASSWORD")

if not username or not password:
    logger.error("USER and PASSWORD environment variables must be set in .env file")
    sys.exit(1)

logger.info(f"Starting GNS3 MCP HTTP server on {http_host}:{http_port}")
logger.info(f"GNS3 server: {gns3_host}:{gns3_port}")

# Override sys.argv to pass HTTP transport arguments
sys.argv = [
    "main.py",
    "--transport", "http",
    "--http-host", http_host,
    "--http-port", str(http_port),
    "--host", gns3_host,
    "--port", str(gns3_port),
    "--username", username,
    "--password", password
]

logger.info("Starting FastMCP server...")

# Execute main.py directly (it has no main() function)
try:
    main_py_path = script_dir / "server" / "main.py"
    with open(main_py_path) as f:
        code = f.read()

    # Provide globals needed by main.py
    exec_globals = {
        "__name__": "__main__",
        "__file__": str(main_py_path)
    }
    exec(code, exec_globals)
except KeyboardInterrupt:
    logger.info("Server stopped by user")
    sys.exit(0)
except Exception as e:
    logger.error(f"Server failed to start: {e}", exc_info=True)
    sys.exit(1)
