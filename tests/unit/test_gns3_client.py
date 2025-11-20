"""Unit tests for GNS3Client (gns3_client.py)

Tests GNS3 API v3 client with mocked HTTP responses.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from gns3_client import GNS3Client

# ===== Fixtures =====


@pytest.fixture
def client():
    """GNS3Client instance for testing"""
    return GNS3Client(host="testhost", port=8080, username="testuser", password="testpass")


@pytest.fixture
def authenticated_client(client):
    """Authenticated GNS3Client"""
    client.token = "test-jwt-token"
    return client


# ===== Initialization Tests =====


class TestGNS3ClientInit:
    """Tests for GNS3Client initialization"""

    def test_init_sets_base_url(self, client):
        """Test initialization sets correct base URL"""
        assert client.base_url == "http://testhost:8080"

    def test_init_sets_credentials(self, client):
        """Test initialization stores credentials"""
        assert client.username == "testuser"
        assert client.password == "testpass"

    def test_init_no_token(self, client):
        """Test initialization without token"""
        assert client.token is None

    def test_init_creates_async_client(self, client):
        """Test initialization creates httpx AsyncClient"""
        assert isinstance(client.client, httpx.AsyncClient)


# ===== Authentication Tests =====


class TestAuthentication:
    """Tests for authenticate()"""

    @pytest.mark.asyncio
    async def test_successful_authentication(self, client):
        """Test successful authentication"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "jwt-token-123", "token_type": "bearer"}
        mock_response.raise_for_status = MagicMock()

        client.client.post = AsyncMock(return_value=mock_response)

        result = await client.authenticate()

        assert result is True
        assert client.token == "jwt-token-123"
        client.client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_authentication_failure(self, client):
        """Test authentication failure"""
        client.client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
            )
        )

        result = await client.authenticate()

        assert result is False
        assert client.token is None

    @pytest.mark.asyncio
    async def test_authentication_network_error(self, client):
        """Test authentication with network error"""
        client.client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await client.authenticate()

        assert result is False


# ===== Headers Tests =====


class TestHeaders:
    """Tests for _headers()"""

    def test_headers_with_token(self, authenticated_client):
        """Test headers include Bearer token"""
        headers = authenticated_client._headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-jwt-token"

    def test_headers_without_token(self, client):
        """Test headers fail without authentication"""
        with pytest.raises(RuntimeError) as exc:
            client._headers()
        assert "GNS3 server unavailable" in str(exc.value)


# ===== Error Extraction Tests =====


class TestExtractError:
    """Tests for _extract_error()"""

    def test_extract_http_error_with_json(self, client):
        """Test extracting error from HTTP response with JSON"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "Node not found"}
        mock_response.status_code = 404

        exc = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=mock_response)

        error_msg = client._extract_error(exc)
        assert "Node not found" in error_msg

    def test_extract_http_error_without_json(self, client):
        """Test extracting error from HTTP response without JSON"""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error Details"

        exc = httpx.HTTPStatusError(
            "500 Internal Server Error", request=MagicMock(), response=mock_response
        )

        error_msg = client._extract_error(exc)
        assert "HTTP 500" in error_msg

    def test_extract_generic_exception(self, client):
        """Test extracting error from generic exception"""
        exc = ValueError("Something went wrong")
        error_msg = client._extract_error(exc)
        assert "Something went wrong" in error_msg


# ===== Project Methods Tests =====


class TestProjectMethods:
    """Tests for project-related methods"""

    @pytest.mark.asyncio
    async def test_get_projects(self, authenticated_client):
        """Test getting projects list"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"project_id": "proj-1", "name": "Project 1"},
            {"project_id": "proj-2", "name": "Project 2"},
        ]
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        projects = await authenticated_client.get_projects()

        assert len(projects) == 2
        assert projects[0]["project_id"] == "proj-1"

    @pytest.mark.asyncio
    async def test_open_project(self, authenticated_client):
        """Test opening a project"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "project_id": "proj-1",
            "name": "Test Project",
            "status": "opened",
        }
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        project = await authenticated_client.open_project("proj-1")

        assert project["status"] == "opened"
        authenticated_client.client.post.assert_called_once()


# ===== Node Methods Tests =====


class TestNodeMethods:
    """Tests for node-related methods"""

    @pytest.mark.asyncio
    async def test_get_nodes(self, authenticated_client):
        """Test getting nodes list"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"node_id": "node-1", "name": "Router1"},
            {"node_id": "node-2", "name": "Router2"},
        ]
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        nodes = await authenticated_client.get_nodes("proj-1")

        assert len(nodes) == 2
        assert nodes[0]["name"] == "Router1"

    @pytest.mark.asyncio
    async def test_start_node(self, authenticated_client):
        """Test starting a node"""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        result = await authenticated_client.start_node("proj-1", "node-1")

        # Empty response should return empty dict
        assert result == {}

    @pytest.mark.asyncio
    async def test_stop_node(self, authenticated_client):
        """Test stopping a node"""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        result = await authenticated_client.stop_node("proj-1", "node-1")

        assert result == {}

    @pytest.mark.asyncio
    async def test_update_node(self, authenticated_client):
        """Test updating a node"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "node_id": "node-1",
            "name": "UpdatedName",
            "x": 200,
            "y": 300,
        }
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.put = AsyncMock(return_value=mock_response)

        properties = {"name": "UpdatedName", "x": 200, "y": 300}
        result = await authenticated_client.update_node("proj-1", "node-1", properties)

        assert result["name"] == "UpdatedName"
        assert result["x"] == 200

    @pytest.mark.asyncio
    async def test_delete_node(self, authenticated_client):
        """Test deleting a node"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.delete = AsyncMock(return_value=mock_response)

        await authenticated_client.delete_node("proj-1", "node-1")

        authenticated_client.client.delete.assert_called_once()


# ===== Link Methods Tests =====


class TestLinkMethods:
    """Tests for link-related methods"""

    @pytest.mark.asyncio
    async def test_get_links(self, authenticated_client):
        """Test getting links list"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"link_id": "link-1", "link_type": "ethernet"},
            {"link_id": "link-2", "link_type": "ethernet"},
        ]
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        links = await authenticated_client.get_links("proj-1")

        assert len(links) == 2
        assert links[0]["link_id"] == "link-1"

    @pytest.mark.asyncio
    async def test_create_link(self, authenticated_client):
        """Test creating a link"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"link_id": "new-link", "link_type": "ethernet"}
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        link_spec = {
            "nodes": [
                {"node_id": "node-1", "adapter_number": 0, "port_number": 0},
                {"node_id": "node-2", "adapter_number": 0, "port_number": 0},
            ]
        }

        result = await authenticated_client.create_link("proj-1", link_spec)

        assert result["link_id"] == "new-link"

    @pytest.mark.asyncio
    async def test_delete_link(self, authenticated_client):
        """Test deleting a link"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.delete = AsyncMock(return_value=mock_response)

        await authenticated_client.delete_link("proj-1", "link-1")

        authenticated_client.client.delete.assert_called_once()


# ===== Template Methods Tests =====


class TestTemplateMethods:
    """Tests for template-related methods"""

    @pytest.mark.asyncio
    async def test_get_templates(self, authenticated_client):
        """Test getting templates list"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"template_id": "tmpl-1", "name": "Router"},
            {"template_id": "tmpl-2", "name": "Switch"},
        ]
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        templates = await authenticated_client.get_templates()

        assert len(templates) == 2
        assert templates[0]["name"] == "Router"

    @pytest.mark.asyncio
    async def test_get_template(self, authenticated_client):
        """Test getting single template"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"template_id": "tmpl-1", "name": "Router"}
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        template = await authenticated_client.get_template("tmpl-1")

        assert template["name"] == "Router"

    @pytest.mark.asyncio
    async def test_create_node_from_template(self, authenticated_client):
        """Test creating node from template"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"node_id": "new-node", "name": "Router1"}
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        payload = {"x": 100, "y": 200, "name": "Router1"}
        result = await authenticated_client.create_node_from_template("proj-1", "tmpl-1", payload)

        assert result["node_id"] == "new-node"


# ===== Drawing Methods Tests =====


class TestDrawingMethods:
    """Tests for drawing-related methods"""

    @pytest.mark.asyncio
    async def test_get_drawings(self, authenticated_client):
        """Test getting drawings list"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"drawing_id": "draw-1", "x": 100, "y": 200},
            {"drawing_id": "draw-2", "x": 300, "y": 400},
        ]
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        drawings = await authenticated_client.get_drawings("proj-1")

        assert len(drawings) == 2
        assert drawings[0]["x"] == 100

    @pytest.mark.asyncio
    async def test_create_drawing(self, authenticated_client):
        """Test creating a drawing"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"drawing_id": "new-draw", "x": 100, "y": 200}
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        drawing_data = {"x": 100, "y": 200, "svg": "<rect/>"}

        result = await authenticated_client.create_drawing("proj-1", drawing_data)

        assert result["drawing_id"] == "new-draw"

    @pytest.mark.asyncio
    async def test_delete_drawing(self, authenticated_client):
        """Test deleting a drawing"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.delete = AsyncMock(return_value=mock_response)

        await authenticated_client.delete_drawing("proj-1", "draw-1")

        authenticated_client.client.delete.assert_called_once()


# ===== Edge Cases Tests =====


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_http_error_raises(self, authenticated_client):
        """Test HTTP errors are raised"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )

        authenticated_client.client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await authenticated_client.get_projects()

    @pytest.mark.asyncio
    async def test_empty_response_handling(self, authenticated_client):
        """Test handling empty responses (HTTP 204)"""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        authenticated_client.client.post = AsyncMock(return_value=mock_response)

        result = await authenticated_client.start_node("proj-1", "node-1")

        # Should return empty dict, not raise exception
        assert result == {}
