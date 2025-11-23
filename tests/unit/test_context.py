"""Unit tests for context.py helpers (v0.50.0, GM-47)

Tests global context management and helper functions.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "gns3_mcp" / "server"))

from unittest.mock import AsyncMock, MagicMock

from context import clear_app, get_app, get_dependencies, set_app, validate_current_project
from di_container import Dependencies
from interfaces import IAppContext

# ===== Test Fixtures =====


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext for testing"""
    mock_app = MagicMock(spec=IAppContext)
    mock_app.current_project_id = None
    mock_app.dependencies = Dependencies()

    # Mock gns3 client
    mock_gns3 = MagicMock()
    mock_gns3.get_projects = AsyncMock(return_value=[])
    mock_app.gns3 = mock_gns3

    return mock_app


# ===== Global App Context Tests =====


class TestGlobalAppContext:
    """Tests for get_app/set_app/clear_app"""

    def test_get_app_raises_when_not_initialized(self):
        """Test get_app raises RuntimeError when app not initialized"""
        # Clear any existing app
        clear_app()

        with pytest.raises(RuntimeError) as exc_info:
            get_app()

        assert "not initialized" in str(exc_info.value).lower()

    def test_set_app_stores_context(self, mock_app_context):
        """Test set_app stores the app context"""
        set_app(mock_app_context)

        # Should be able to retrieve it
        app = get_app()
        assert app is mock_app_context

    def test_clear_app_removes_context(self, mock_app_context):
        """Test clear_app removes the stored context"""
        set_app(mock_app_context)
        assert get_app() is mock_app_context

        clear_app()

        # Should raise after clearing
        with pytest.raises(RuntimeError):
            get_app()

    def test_set_app_overwrites_previous(self, mock_app_context):
        """Test set_app overwrites previously set context"""
        first_app = mock_app_context
        second_app = MagicMock(spec=IAppContext)

        set_app(first_app)
        assert get_app() is first_app

        set_app(second_app)
        assert get_app() is second_app
        assert get_app() is not first_app


# ===== Dependencies Helper Tests =====


class TestGetDependencies:
    """Tests for get_dependencies helper"""

    def test_get_dependencies_returns_container(self, mock_app_context):
        """Test get_dependencies returns DI container from app"""
        deps = Dependencies()
        mock_app_context.dependencies = deps

        set_app(mock_app_context)

        retrieved = get_dependencies()
        assert retrieved is deps

    def test_get_dependencies_raises_when_app_not_initialized(self):
        """Test get_dependencies raises when app not initialized"""
        clear_app()

        with pytest.raises(RuntimeError) as exc_info:
            get_dependencies()

        assert "not initialized" in str(exc_info.value).lower()


# ===== Project Validation Tests =====


class TestValidateCurrentProject:
    """Tests for validate_current_project helper"""

    @pytest.mark.asyncio
    async def test_auto_connect_to_opened_project(self, mock_app_context):
        """Test auto-connects to opened project when none connected"""
        # Setup: No current project, but one is opened in GNS3
        mock_app_context.current_project_id = None
        mock_app_context.gns3.get_projects.return_value = [
            {"project_id": "abc123", "name": "TestProject", "status": "opened"}
        ]

        result = await validate_current_project(mock_app_context)

        # Should auto-connect
        assert result is None  # No error
        assert mock_app_context.current_project_id == "abc123"

    @pytest.mark.asyncio
    async def test_no_project_open_returns_error(self, mock_app_context):
        """Test returns error when no project is opened"""
        # Setup: No current project, no opened projects
        mock_app_context.current_project_id = None
        mock_app_context.gns3.get_projects.return_value = [
            {"project_id": "abc123", "name": "ClosedProject", "status": "closed"}
        ]

        result = await validate_current_project(mock_app_context)

        # Should return error
        assert result is not None
        error = json.loads(result)
        assert "No project opened" in error["error"]
        assert "open_project" in error["suggested_action"]

    @pytest.mark.asyncio
    async def test_project_still_exists_and_opened(self, mock_app_context):
        """Test validates connected project still exists and is opened"""
        # Setup: Already connected to a project that's still opened
        mock_app_context.current_project_id = "abc123"
        mock_app_context.gns3.get_projects.return_value = [
            {"project_id": "abc123", "name": "TestProject", "status": "opened"}
        ]

        result = await validate_current_project(mock_app_context)

        # Should pass validation
        assert result is None
        assert mock_app_context.current_project_id == "abc123"

    @pytest.mark.asyncio
    async def test_project_no_longer_exists(self, mock_app_context):
        """Test returns error when connected project no longer exists"""
        # Setup: Connected to project that no longer exists
        mock_app_context.current_project_id = "deleted-project"
        mock_app_context.gns3.get_projects.return_value = [
            {"project_id": "abc123", "name": "OtherProject", "status": "opened"}
        ]

        result = await validate_current_project(mock_app_context)

        # Should return error and clear project ID
        assert result is not None
        assert mock_app_context.current_project_id is None
        error = json.loads(result)
        assert "no longer exists" in error["error"].lower()

    @pytest.mark.asyncio
    async def test_project_is_closed(self, mock_app_context):
        """Test returns error when connected project is closed"""
        # Setup: Connected to project that's now closed
        mock_app_context.current_project_id = "abc123"
        mock_app_context.gns3.get_projects.return_value = [
            {"project_id": "abc123", "name": "ClosedProject", "status": "closed"}
        ]

        result = await validate_current_project(mock_app_context)

        # Should return error and clear project ID
        assert result is not None
        assert mock_app_context.current_project_id is None
        error = json.loads(result)
        assert "closed" in error["error"].lower()

    @pytest.mark.asyncio
    async def test_multiple_opened_projects_connects_to_first(self, mock_app_context):
        """Test connects to first project when multiple are opened"""
        # Setup: No current project, multiple opened projects
        mock_app_context.current_project_id = None
        mock_app_context.gns3.get_projects.return_value = [
            {"project_id": "first", "name": "FirstProject", "status": "opened"},
            {"project_id": "second", "name": "SecondProject", "status": "opened"},
        ]

        result = await validate_current_project(mock_app_context)

        # Should connect to first one
        assert result is None
        assert mock_app_context.current_project_id == "first"

    @pytest.mark.asyncio
    async def test_api_error_returns_error(self, mock_app_context):
        """Test returns error when GNS3 API fails"""
        # Setup: API raises exception
        mock_app_context.current_project_id = None
        mock_app_context.gns3.get_projects.side_effect = Exception("API Error")

        result = await validate_current_project(mock_app_context)

        # Should return error
        assert result is not None
        error = json.loads(result)
        assert "Failed to validate" in error["error"]
        assert "API Error" in error["details"]


# ===== Integration Tests =====


class TestContextIntegration:
    """Integration tests for context management"""

    def test_full_lifecycle(self, mock_app_context):
        """Test full app context lifecycle: set -> get -> clear"""
        # Initially not set
        clear_app()
        with pytest.raises(RuntimeError):
            get_app()

        # Set app
        set_app(mock_app_context)
        assert get_app() is mock_app_context

        # Get dependencies
        deps = get_dependencies()
        assert deps is mock_app_context.dependencies

        # Clear app
        clear_app()
        with pytest.raises(RuntimeError):
            get_app()
        with pytest.raises(RuntimeError):
            get_dependencies()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
