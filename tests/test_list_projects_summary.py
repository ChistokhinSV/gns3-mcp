"""
Test for list_projects_impl with ProjectSummary model

Tests that the function returns ProjectSummary with uri field
"""

import sys
from pathlib import Path

# Add mcp-server/server to path
server_path = Path(__file__).parent.parent / "mcp-server" / "server"
sys.path.insert(0, str(server_path))

import pytest
from unittest.mock import AsyncMock, MagicMock
import json


# Mock the AppContext
class MockAppContext:
    def __init__(self, projects_data):
        self.gns3 = MagicMock()
        self.gns3.get_projects = AsyncMock(return_value=projects_data)


# Sample input data
SAMPLE_PROJECTS_DATA = [
    {
        "name": "Test LAB",
        "project_id": "79d09537-5b07-4af6-8308-bd1846f6d267",
        "status": "opened",
        "path": "/opt/gns3/projects/79d09537-5b07-4af6-8308-bd1846f6d267",
        "filename": "Test LAB.gns3"
    },
    {
        "name": "Test DNS HA",
        "project_id": "00700165-3140-4a1e-b3f0-0a11eb15ab47",
        "status": "closed",
        "path": "/opt/gns3/projects/00700165-3140-4a1e-b3f0-0a11eb15ab47",
        "filename": "Test DNS HA.gns3"
    }
]


@pytest.mark.asyncio
async def test_list_projects_summary():
    """Test that list_projects_impl returns ProjectSummary with uri field"""
    from resources.project_resources import list_projects_impl

    # Create mock context
    app = MockAppContext(SAMPLE_PROJECTS_DATA)

    # Call the function (default: detailed=False)
    result = await list_projects_impl(app, detailed=False)

    # Parse JSON result
    result_data = json.loads(result)

    # Expected output (ProjectSummary format with uri)
    expected_data = [
        {
            "status": "opened",
            "name": "Test LAB",
            "uri": "projects://79d09537-5b07-4af6-8308-bd1846f6d267"
        },
        {
            "status": "closed",
            "name": "Test DNS HA",
            "uri": "projects://00700165-3140-4a1e-b3f0-0a11eb15ab47"
        }
    ]

    # Verify the result
    assert result_data == expected_data, f"Expected:\n{json.dumps(expected_data, indent=2)}\n\nGot:\n{json.dumps(result_data, indent=2)}"
    print("[PASS] Test passed: ProjectSummary format with uri is correct")


@pytest.mark.asyncio
async def test_list_projects_detailed():
    """Test that list_projects_impl returns full data when detailed=True"""
    from resources.project_resources import list_projects_impl

    # Create mock context
    app = MockAppContext(SAMPLE_PROJECTS_DATA)

    # Call the function with detailed=True
    result = await list_projects_impl(app, detailed=True)

    # Parse JSON result
    result_data = json.loads(result)

    # Should return full project data
    assert result_data == SAMPLE_PROJECTS_DATA, f"Expected full data, got:\n{json.dumps(result_data, indent=2)}"
    print("[PASS] Test passed: Detailed mode returns full project data")


@pytest.mark.asyncio
async def test_list_projects_empty():
    """Test that list_projects_impl handles empty project list"""
    from resources.project_resources import list_projects_impl

    # Create mock context with empty projects
    app = MockAppContext([])

    # Call the function
    result = await list_projects_impl(app)

    # Parse JSON result
    result_data = json.loads(result)

    # Expected output for empty list
    expected_data = []

    # Verify the result
    assert result_data == expected_data, f"Expected empty array, got: {result_data}"
    print("[PASS] Test passed: Empty list handled correctly")


if __name__ == "__main__":
    # Run tests manually
    import asyncio

    print("Running test_list_projects_summary...")
    asyncio.run(test_list_projects_summary())

    print("\nRunning test_list_projects_detailed...")
    asyncio.run(test_list_projects_detailed())

    print("\nRunning test_list_projects_empty...")
    asyncio.run(test_list_projects_empty())

    print("\n[PASS] All tests passed!")
