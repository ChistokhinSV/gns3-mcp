"""
Test for list_projects_impl with ProjectSummary model

Tests that the function returns ProjectSummary with uri field
"""

import sys
from pathlib import Path

# Add gns3_mcp/server to path
server_path = Path(__file__).parent.parent / "gns3_mcp" / "server"
sys.path.insert(0, str(server_path))

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


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
        "filename": "Test LAB.gns3",
    },
    {
        "name": "Test DNS HA",
        "project_id": "00700165-3140-4a1e-b3f0-0a11eb15ab47",
        "status": "closed",
        "path": "/opt/gns3/projects/00700165-3140-4a1e-b3f0-0a11eb15ab47",
        "filename": "Test DNS HA.gns3",
    },
]


@pytest.mark.asyncio
async def test_list_projects_summary():
    """Test that list_projects_impl returns formatted table with uri field"""
    from resources.project_resources import list_projects_impl

    # Create mock context
    app = MockAppContext(SAMPLE_PROJECTS_DATA)

    # Call the function (default: detailed=False)
    result = await list_projects_impl(app, detailed=False)

    # Verify it's a string (table format)
    assert isinstance(result, str), f"Expected string, got {type(result)}"

    # Verify table contains expected data
    assert "opened" in result, "Expected 'opened' status in table"
    assert "closed" in result, "Expected 'closed' status in table"
    assert "Test LAB" in result, "Expected 'Test LAB' in table"
    assert "Test DNS HA" in result, "Expected 'Test DNS HA' in table"
    assert "projects://79d09537-5b07-4af6-8308-bd1846f6d267" in result, "Expected URI in table"
    assert "projects://00700165-3140-4a1e-b3f0-0a11eb15ab47" in result, "Expected URI in table"

    print("[PASS] Test passed: Table format with uri is correct")


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
    assert (
        result_data == SAMPLE_PROJECTS_DATA
    ), f"Expected full data, got:\n{json.dumps(result_data, indent=2)}"
    print("[PASS] Test passed: Detailed mode returns full project data")


@pytest.mark.asyncio
async def test_list_projects_empty():
    """Test that list_projects_impl handles empty project list"""
    from resources.project_resources import list_projects_impl

    # Create mock context with empty projects
    app = MockAppContext([])

    # Call the function (default: detailed=False)
    result = await list_projects_impl(app, detailed=False)

    # Verify it's a string (table format shows "No items found" for empty list)
    assert isinstance(result, str), f"Expected string, got {type(result)}"
    assert "No items found" in result, f"Expected 'No items found' message, got: {result}"

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
