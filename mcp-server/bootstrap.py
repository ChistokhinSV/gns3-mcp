#!/usr/bin/env python3
"""Bootstrap script for GNS3 MCP Server - handles runtime dependency installation with UV.

This wrapper:
1. Creates a virtual environment on first run using UV package manager
2. Installs dependencies from requirements.txt (matches user's Python version)
3. Launches the actual MCP server from venv

Benefits:
- Works with any Python 3.10-3.13 (binary wheels match runtime)
- UV package manager: 10-100× faster than pip (5-8s install vs 15-30s)
- Package size: ~60 MB (.mcpb includes UV binary)
- One-time setup delay (~5-10s), then instant startup
"""

import os
import sys
import subprocess
import hashlib
import logging
from pathlib import Path

# Configure logging to stderr (Claude Desktop captures this)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] GNS3-MCP Bootstrap: %(message)s",
    datefmt="%H:%M:%S %d.%m.%Y",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def get_extension_dir():
    """Get the directory where this script lives (the .mcpb extraction dir)."""
    return Path(__file__).parent.absolute()


def get_venv_dir(extension_dir):
    """Get the venv directory path."""
    return extension_dir / "venv"


def get_requirements_file(extension_dir):
    """Get the requirements.txt file path."""
    return extension_dir / "requirements.txt"


def get_uv_path(extension_dir):
    """Get path to bundled UV package manager executable."""
    if sys.platform == "win32":
        return extension_dir / "uv.exe"
    else:
        return extension_dir / "uv"  # Unix/macOS


def get_requirements_hash(requirements_file):
    """Calculate hash of requirements.txt to detect changes."""
    if not requirements_file.exists():
        return None

    content = requirements_file.read_text()
    return hashlib.md5(content.encode()).hexdigest()


def get_venv_hash_file(venv_dir):
    """Get the file storing the requirements.txt hash."""
    return venv_dir / ".requirements_hash"


def venv_needs_update(venv_dir, requirements_file):
    """Check if venv needs to be created or updated."""
    # Check if venv exists
    if not venv_dir.exists():
        logger.info("Virtual environment not found - will create")
        return True

    # Check if venv is valid (has python executable)
    venv_python = get_venv_python(venv_dir)
    if not venv_python.exists():
        logger.warning("Virtual environment incomplete - will recreate")
        return True

    # Check if requirements.txt changed
    hash_file = get_venv_hash_file(venv_dir)
    if not hash_file.exists():
        logger.info("Requirements hash not found - will update venv")
        return True

    current_hash = get_requirements_hash(requirements_file)
    stored_hash = hash_file.read_text().strip()

    if current_hash != stored_hash:
        logger.info("Requirements changed - will update venv")
        return True

    logger.info("Virtual environment up-to-date")
    return False


def get_venv_python(venv_dir):
    """Get the Python executable path in venv (cross-platform)."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    else:
        return venv_dir / "bin" / "python"


def create_venv(venv_dir, uv_path):
    """Create a virtual environment using UV package manager."""
    logger.info(f"Creating virtual environment at: {venv_dir}")

    try:
        # Remove old venv if exists
        if venv_dir.exists():
            import shutil
            logger.info("Removing old venv...")
            shutil.rmtree(venv_dir)

        # Create new venv with UV
        logger.info("Running: uv venv ...")
        result = subprocess.run(
            [str(uv_path), "venv", str(venv_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("VENV CREATION FAILED:")
            logger.error(f"Exit code: {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )

        logger.info("Virtual environment created successfully (~1-2 seconds)")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create virtual environment")
        logger.error(f"Command: {' '.join(str(x) for x in e.cmd)}")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"Output: {e.output if hasattr(e, 'output') else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating venv: {type(e).__name__}: {e}")
        raise


def install_dependencies(venv_dir, requirements_file, uv_path):
    """Install dependencies from requirements.txt using UV (10-100× faster than pip)."""
    logger.info("Installing dependencies from requirements.txt...")
    logger.info(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    logger.info("Using UV package manager for fast installation...")

    venv_python = get_venv_python(venv_dir)

    try:
        # Install requirements with UV (no pip upgrade needed)
        # UV requires --python flag to target specific venv
        logger.info("Installing requirements (5-8 seconds with UV)...")
        result = subprocess.run(
            [
                str(uv_path),
                "pip",
                "install",
                "--python",
                str(venv_python),
                "-r",
                str(requirements_file),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error("DEPENDENCY INSTALLATION FAILED:")
            logger.error(f"Exit code: {result.returncode}")
            logger.error("STDERR:")
            logger.error(result.stderr)
            logger.error("STDOUT:")
            logger.error(result.stdout)
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )

        logger.info("Dependencies installed successfully")

        # Save requirements hash
        hash_file = get_venv_hash_file(venv_dir)
        current_hash = get_requirements_hash(requirements_file)
        hash_file.write_text(current_hash)
        logger.info(f"Saved requirements hash: {current_hash}")

    except subprocess.CalledProcessError as e:
        logger.error("Failed to install dependencies")
        logger.error(f"Command: {' '.join(str(x) for x in e.cmd)}")
        logger.error(f"Exit code: {e.returncode}")
        logger.error("This usually means:")
        logger.error("  1. No internet connection")
        logger.error("  2. PyPI is unreachable")
        logger.error("  3. Dependencies incompatible with your Python version")
        raise
    except Exception as e:
        logger.error(f"Unexpected error installing dependencies: {type(e).__name__}: {e}")
        raise


def launch_server(venv_dir, extension_dir, args):
    """Launch the actual MCP server from venv."""
    venv_python = get_venv_python(venv_dir)
    server_main = extension_dir / "gns3_mcp" / "server" / "main.py"

    logger.info(f"Launching GNS3 MCP Server: {server_main}")
    logger.info(f"Python executable: {venv_python}")
    logger.info(f"Arguments: {args}")

    # Use subprocess instead of execv (Windows path resolution issue)
    # execv() on Windows has issues with symlinks/junctions used by Claude Desktop
    cmd = [str(venv_python), str(server_main)] + args

    try:
        # Use subprocess.run() with no capture to pass through stdin/stdout/stderr
        # This allows MCP protocol communication over stdio
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        logger.error(f"Failed to launch server: {e}")
        sys.exit(1)


def check_python_version():
    """Check if Python version is supported."""
    major = sys.version_info.major
    minor = sys.version_info.minor
    micro = sys.version_info.micro

    if major != 3:
        logger.error(f"Python {major}.{minor}.{micro} not supported - requires Python 3.x")
        return False

    if minor < 10:
        logger.error(f"Python {major}.{minor}.{micro} not supported - requires Python 3.10+")
        return False

    if minor >= 14:
        logger.error(f"Python {major}.{minor}.{micro} not supported - alpha/beta version")
        logger.error("Please install Python 3.10, 3.11, 3.12, or 3.13")
        return False

    if minor == 13 and micro >= 0:
        logger.warning(f"Python {major}.{minor}.{micro} detected - latest stable")
        logger.warning("Some dependencies might not have wheels yet")
        logger.warning("Consider Python 3.11 or 3.12 for best compatibility")

    logger.info(f"Python {major}.{minor}.{micro} supported")
    return True


def main():
    """Main bootstrap logic."""
    logger.info("=" * 60)
    logger.info("GNS3 MCP Server Bootstrap Starting")
    logger.info("=" * 60)

    # Get paths
    extension_dir = get_extension_dir()
    venv_dir = get_venv_dir(extension_dir)
    requirements_file = get_requirements_file(extension_dir)
    uv_path = get_uv_path(extension_dir)

    logger.info(f"Extension directory: {extension_dir}")
    logger.info(f"System Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # Check Python version
    if not check_python_version():
        logger.error("=" * 60)
        logger.error("UNSUPPORTED PYTHON VERSION")
        logger.error("=" * 60)
        logger.error("GNS3 MCP Server requires Python 3.10, 3.11, 3.12, or 3.13")
        logger.error(f"You have: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        logger.error("")
        logger.error("Please install a supported Python version:")
        logger.error("  https://www.python.org/downloads/")
        sys.exit(1)

    # Check if UV binary exists
    if not uv_path.exists():
        logger.error(f"UV binary not found at: {uv_path}")
        logger.error("This is a packaging error - please report this issue")
        logger.error("Expected UV package manager to be bundled with extension")
        sys.exit(1)

    # Check if requirements.txt exists
    if not requirements_file.exists():
        logger.error(f"requirements.txt not found at: {requirements_file}")
        logger.error("This is a packaging error - please report this issue")
        sys.exit(1)

    # Check if venv needs setup/update
    if venv_needs_update(venv_dir, requirements_file):
        logger.info("Setting up virtual environment with UV (one-time, ~5-10 seconds)...")
        create_venv(venv_dir, uv_path)
        install_dependencies(venv_dir, requirements_file, uv_path)
        logger.info("Setup complete!")

    # Launch the actual server
    logger.info("=" * 60)
    launch_server(venv_dir, extension_dir, sys.argv[1:])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bootstrap interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Bootstrap failed: {e}", exc_info=True)
        sys.exit(1)
