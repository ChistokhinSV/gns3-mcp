"""Version Synchronization Tests

Tests to ensure version is read from manifest.json and included in error responses.
"""

import json
from pathlib import Path

import pytest


def test_version_synchronization():
    """Verify version is read from manifest.json"""
    # Read manifest version
    manifest_path = Path(__file__).parent.parent.parent / "mcp-server" / "manifest.json"
    with open(manifest_path) as f:
        manifest_version = json.load(f)["version"]

    # Import server version
    import sys

    server_path = Path(__file__).parent.parent.parent / "gns3_mcp" / "server"
    sys.path.insert(0, str(server_path))

    from main import VERSION

    # Assert they match
    assert (
        manifest_version == VERSION
    ), f"Version mismatch: main.py={VERSION}, manifest.json={manifest_version}"


def test_version_in_error_response():
    """Verify all error responses include server version"""
    import sys
    from pathlib import Path

    server_path = Path(__file__).parent.parent.parent / "gns3_mcp" / "server"
    sys.path.insert(0, str(server_path))

    from main import VERSION
    from models import ErrorResponse

    # Create error response
    error = ErrorResponse(error="Test error", details="Test details", server_version=VERSION)

    # Verify server_version is present
    assert hasattr(error, "server_version"), "ErrorResponse must have server_version field"
    assert (
        error.server_version == VERSION
    ), f"server_version should be {VERSION}, got {error.server_version}"

    # Verify timestamp is present
    assert hasattr(error, "timestamp"), "ErrorResponse must have timestamp field"
    assert error.timestamp is not None, "timestamp should not be None"


def test_error_response_model_dump():
    """Verify ErrorResponse includes version when serialized to JSON"""
    import sys
    from pathlib import Path

    server_path = Path(__file__).parent.parent.parent / "gns3_mcp" / "server"
    sys.path.insert(0, str(server_path))

    from main import VERSION
    from models import ErrorResponse

    # Create error response
    error = ErrorResponse(error="Test error", server_version=VERSION)

    # Serialize to dict
    error_dict = error.model_dump()

    # Verify all fields present
    assert "error" in error_dict
    assert "server_version" in error_dict
    assert "timestamp" in error_dict
    assert error_dict["server_version"] == VERSION


def test_version_not_hardcoded():
    """Verify VERSION is not hardcoded in main.py (v0.42.0: PyPI package structure)"""
    main_file = Path(__file__).parent.parent.parent / "gns3_mcp" / "server" / "main.py"
    main_content = main_file.read_text()

    # Check for version reading code (v0.42.0: Read from package __init__)
    assert (
        "from gns3_mcp import __version__" in main_content
    ), "main.py should import version from gns3_mcp package"
    assert "VERSION = __version__" in main_content, "main.py should set VERSION from __version__"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
