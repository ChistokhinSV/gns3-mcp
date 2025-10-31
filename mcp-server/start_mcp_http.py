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
import runpy
import signal
from pathlib import Path
from datetime import datetime

# Add lib/ and server/ to path (need lib/ for dotenv and other dependencies)
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / "lib"))
sys.path.insert(0, str(script_dir / "server"))

# Validate .env file exists
env_path = script_dir.parent / ".env"
if not env_path.exists():
    print(f"ERROR: .env file not found at: {env_path}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Create .env file with required variables:", file=sys.stderr)
    print("  USER=admin", file=sys.stderr)
    print("  PASSWORD=your_gns3_password", file=sys.stderr)
    print("  GNS3_HOST=192.168.1.20", file=sys.stderr)
    print("  GNS3_PORT=80", file=sys.stderr)
    print("  HTTP_HOST=127.0.0.1", file=sys.stderr)
    print("  HTTP_PORT=8100", file=sys.stderr)
    print("  LOG_LEVEL=INFO", file=sys.stderr)
    sys.exit(1)

# Load environment variables
from dotenv import load_dotenv
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

# Validate required credentials
if not username or not password:
    logger.error(f".env file missing required variables: USER and/or PASSWORD")
    logger.error(f".env location: {env_path}")
    sys.exit(1)

logger.info(f"GNS3 MCP HTTP Server v0.41.0")
logger.info(f"Python: {sys.version.split()[0]} ({sys.executable})")
logger.info(f"HTTP endpoint: http://{http_host}:{http_port}/mcp/")
logger.info(f"GNS3 server: {gns3_host}:{gns3_port}")
logger.info(f"Log file: {script_dir.parent / 'mcp-http-server.log'}")

# Auto-generate MCP_API_KEY if not in .env (for HTTP authentication)
import secrets
api_key = os.getenv("MCP_API_KEY")
if not api_key:
    api_key = secrets.token_urlsafe(32)
    logger.warning("=" * 70)
    logger.warning("WARNING: MCP_API_KEY not found - generated new key")
    logger.warning("=" * 70)
    logger.warning("")

    # Automatically save to .env file for persistence
    try:
        # Read existing .env content
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Check if MCP_API_KEY line exists (even if empty)
        key_line_found = False
        for i, line in enumerate(lines):
            if line.strip().startswith('MCP_API_KEY='):
                # Update existing line
                lines[i] = f"MCP_API_KEY={api_key}\n"
                key_line_found = True
                break

        # If no existing line, append
        if not key_line_found:
            lines.append(f"\n# Auto-generated API key for HTTP mode (v0.41.0)\n")
            lines.append(f"MCP_API_KEY={api_key}\n")

        # Write back to file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        logger.warning(f"API key saved to .env file: {env_path}")
    except Exception as e:
        logger.error(f"Failed to save API key to .env: {e}")
        logger.warning("Please add manually to .env:")
        logger.warning(f"MCP_API_KEY={api_key}")

    logger.warning("")
    logger.warning("Claude Code usage:")
    logger.warning(f'claude mcp add --transport http gns3-lab \\')
    logger.warning(f'  http://127.0.0.1:{http_port}/mcp/ \\')
    logger.warning(f'  --header "MCP_API_KEY: {api_key}"')
    logger.warning("")
    logger.warning("=" * 70)
    # Set for current session
    os.environ["MCP_API_KEY"] = api_key

# Override sys.argv to pass HTTP transport arguments to main.py
# Password removed from argv to prevent process list exposure (CWE-214)
# Password will be read from environment in main.py
sys.argv = [
    "main.py",
    "--transport", "http",
    "--http-host", http_host,
    "--http-port", str(http_port),
    "--host", gns3_host,
    "--port", str(gns3_port),
    "--username", username,
    # Password NOT included - read from PASSWORD env var in main.py
]

logger.info("Starting FastMCP server...")

# Signal handler for graceful shutdown (Windows NSSM service)
def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    # Raise KeyboardInterrupt to trigger uvicorn's shutdown sequence
    raise KeyboardInterrupt

# Register signal handlers
# SIGTERM - sent by NSSM when stopping service
signal.signal(signal.SIGTERM, signal_handler)
# SIGINT - sent by Ctrl+C
signal.signal(signal.SIGINT, signal_handler)
# On Windows, also handle SIGBREAK (Ctrl+Break)
if hasattr(signal, 'SIGBREAK'):
    signal.signal(signal.SIGBREAK, signal_handler)

# Execute main.py as __main__ module using runpy (safer than exec)
try:
    main_py_path = script_dir / "server" / "main.py"
    runpy.run_path(str(main_py_path), run_name="__main__")
except KeyboardInterrupt:
    logger.info("Server stopped by user (Ctrl+C or service stop)")
    # Give lifespan handlers time to complete
    logger.info(" Server shutdown complete")
    sys.exit(0)
except Exception as e:
    logger.error(f"Server failed to start: {e}", exc_info=True)
    sys.exit(1)
