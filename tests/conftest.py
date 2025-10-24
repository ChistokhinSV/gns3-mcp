"""
Pytest configuration and shared fixtures for GNS3 MCP Server tests.

This file contains fixtures that are available to all tests.
"""
import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock

# Add server directory to path for imports
server_path = Path(__file__).parent.parent / "mcp-server" / "server"
sys.path.insert(0, str(server_path))


# ===== Common Fixtures =====

@pytest.fixture
def mock_gns3_client():
    """Mock GNS3Client for testing without actual server connection."""
    from gns3_client import GNS3Client

    client = AsyncMock(spec=GNS3Client)
    # Set up common return values
    client.get_projects.return_value = []
    client.get_nodes.return_value = []
    client.get_links.return_value = []
    client.get_drawings.return_value = []

    return client


@pytest.fixture
def sample_project_data():
    """Sample GNS3 project data for testing."""
    return {
        "project_id": "test-project-123",
        "name": "Test Project",
        "status": "opened",
        "path": "/projects/test-project-123"
    }


@pytest.fixture
def sample_node_data():
    """Sample GNS3 node data for testing."""
    return {
        "node_id": "test-node-123",
        "name": "TestRouter",
        "node_type": "qemu",
        "compute_id": "local",
        "status": "stopped",
        "x": 100,
        "y": 100,
        "z": 1,
        "console": 5000,
        "console_type": "telnet",
        "console_host": "127.0.0.1",
        "label": {
            "text": "TestRouter",
            "x": None,
            "y": -25,
            "rotation": 0,
            "style": "font-family: TypeWriter;font-size: 10.0;font-weight: bold;"
        },
        "symbol": ":/symbols/router.svg",
        "ports": [
            {
                "adapter_number": 0,
                "port_number": 0,
                "name": "eth0",
                "link_type": "ethernet"
            }
        ]
    }


@pytest.fixture
def sample_link_data():
    """Sample GNS3 link data for testing."""
    return {
        "link_id": "test-link-123",
        "link_type": "ethernet",
        "suspend": False,
        "nodes": [
            {
                "node_id": "test-node-1",
                "adapter_number": 0,
                "port_number": 0
            },
            {
                "node_id": "test-node-2",
                "adapter_number": 0,
                "port_number": 0
            }
        ]
    }


@pytest.fixture
def sample_drawing_data():
    """Sample GNS3 drawing data for testing."""
    return {
        "drawing_id": "test-drawing-123",
        "x": 50,
        "y": 50,
        "z": 0,
        "svg": '<rect width="100" height="50" fill="#ffffff" stroke="#000000" stroke-width="2"/>'
    }


@pytest.fixture
def mock_app_context(mock_gns3_client, sample_project_data):
    """Mock application context for testing MCP tools."""
    context = Mock()
    context.gns3 = mock_gns3_client
    context.current_project_id = sample_project_data["project_id"]
    context.console_sessions = {}

    return context


# ===== Pytest Configuration Hooks =====

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (require GNS3 server)")
    config.addinivalue_line("markers", "slow: Slow tests (may take >1s)")
    config.addinivalue_line("markers", "asyncio: Asynchronous tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark async tests
        if "asyncio" in item.keywords:
            item.add_marker(pytest.mark.asyncio)

        # Auto-mark tests in unit/ as unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
