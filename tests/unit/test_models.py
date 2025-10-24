"""Unit tests for Pydantic data models (models.py)

Tests all model validation, serialization, and edge cases.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime

from models import (
    ProjectInfo,
    NodeConsole,
    NodeInfo,
    LinkEndpoint,
    LinkInfo,
    ConnectOperation,
    DisconnectOperation,
    CompletedOperation,
    FailedOperation,
    OperationResult,
    TemplateInfo,
    DrawingInfo,
    ConsoleStatus,
    ErrorResponse,
    validate_connection_operations
)


# ===== ProjectInfo Tests =====

class TestProjectInfo:
    """Tests for ProjectInfo model"""

    def test_valid_project_minimal(self):
        """Test minimal valid project"""
        project = ProjectInfo(
            project_id="test-123",
            name="Test Project",
            status="opened"
        )
        assert project.project_id == "test-123"
        assert project.name == "Test Project"
        assert project.status == "opened"
        assert project.auto_start is False
        assert project.auto_close is True

    def test_valid_project_full(self):
        """Test project with all fields"""
        project = ProjectInfo(
            project_id="test-123",
            name="Test Project",
            status="closed",
            path="/projects/test",
            filename="test.gns3",
            auto_start=True,
            auto_close=False,
            auto_open=True
        )
        assert project.path == "/projects/test"
        assert project.filename == "test.gns3"
        assert project.auto_start is True
        assert project.auto_close is False

    def test_invalid_status(self):
        """Test invalid status value"""
        with pytest.raises(ValidationError) as exc:
            ProjectInfo(
                project_id="test-123",
                name="Test",
                status="invalid"
            )
        assert "status" in str(exc.value)

    def test_missing_required_fields(self):
        """Test missing required fields"""
        with pytest.raises(ValidationError) as exc:
            ProjectInfo(project_id="test-123")
        assert "name" in str(exc.value) or "Field required" in str(exc.value)


# ===== NodeConsole Tests =====

class TestNodeConsole:
    """Tests for NodeConsole model"""

    def test_valid_console(self):
        """Test valid console configuration"""
        console = NodeConsole(
            console_type="telnet",
            console=5000,
            console_host="192.168.1.20"
        )
        assert console.console_type == "telnet"
        assert console.console == 5000
        assert console.console_host == "192.168.1.20"

    def test_optional_fields(self):
        """Test optional console fields"""
        console = NodeConsole(console_type="vnc")
        assert console.console is None
        assert console.console_host is None
        assert console.console_auto_start is False


# ===== NodeInfo Tests =====

class TestNodeInfo:
    """Tests for NodeInfo model"""

    def test_valid_node_minimal(self):
        """Test minimal valid node"""
        node = NodeInfo(
            node_id="node-123",
            name="Router1",
            node_type="qemu",
            status="stopped"
        )
        assert node.node_id == "node-123"
        assert node.name == "Router1"
        assert node.compute_id == "local"
        assert node.x == 0
        assert node.y == 0
        assert node.z == 0

    def test_valid_node_full(self):
        """Test node with all fields"""
        node = NodeInfo(
            node_id="node-123",
            name="Router1",
            node_type="qemu",
            status="started",
            console_type="telnet",
            console=5000,
            console_host="192.168.1.20",
            x=100,
            y=200,
            z=1,
            locked=True,
            ram=1024,
            cpus=2,
            adapters=4
        )
        assert node.x == 100
        assert node.y == 200
        assert node.z == 1
        assert node.locked is True
        assert node.ram == 1024
        assert node.cpus == 2

    def test_invalid_status(self):
        """Test invalid node status"""
        with pytest.raises(ValidationError) as exc:
            NodeInfo(
                node_id="node-123",
                name="Router1",
                node_type="qemu",
                status="invalid"
            )
        assert "status" in str(exc.value)

    def test_valid_statuses(self):
        """Test all valid node statuses"""
        for status in ["started", "stopped", "suspended"]:
            node = NodeInfo(
                node_id="node-123",
                name="Router1",
                node_type="qemu",
                status=status
            )
            assert node.status == status


# ===== LinkEndpoint Tests =====

class TestLinkEndpoint:
    """Tests for LinkEndpoint model"""

    def test_valid_endpoint(self):
        """Test valid link endpoint"""
        endpoint = LinkEndpoint(
            node_id="node-123",
            node_name="Router1",
            adapter_number=0,
            port_number=0
        )
        assert endpoint.node_id == "node-123"
        assert endpoint.adapter_number == 0
        assert endpoint.port_number == 0

    def test_endpoint_with_port_name(self):
        """Test endpoint with port name"""
        endpoint = LinkEndpoint(
            node_id="node-123",
            node_name="Router1",
            adapter_number=0,
            port_number=0,
            port_name="Ethernet0"
        )
        assert endpoint.port_name == "Ethernet0"

    def test_negative_adapter_number(self):
        """Test negative adapter number fails"""
        with pytest.raises(ValidationError) as exc:
            LinkEndpoint(
                node_id="node-123",
                node_name="Router1",
                adapter_number=-1,
                port_number=0
            )
        assert "adapter_number" in str(exc.value)

    def test_negative_port_number(self):
        """Test negative port number fails"""
        with pytest.raises(ValidationError) as exc:
            LinkEndpoint(
                node_id="node-123",
                node_name="Router1",
                adapter_number=0,
                port_number=-1
            )
        assert "port_number" in str(exc.value)

    def test_large_numbers(self):
        """Test large valid adapter/port numbers"""
        endpoint = LinkEndpoint(
            node_id="node-123",
            node_name="Router1",
            adapter_number=99,
            port_number=99
        )
        assert endpoint.adapter_number == 99
        assert endpoint.port_number == 99


# ===== LinkInfo Tests =====

class TestLinkInfo:
    """Tests for LinkInfo model"""

    def test_valid_link(self):
        """Test valid link with endpoints"""
        link = LinkInfo(
            link_id="link-123",
            link_type="ethernet",
            node_a=LinkEndpoint(
                node_id="node-1",
                node_name="Router1",
                adapter_number=0,
                port_number=0
            ),
            node_b=LinkEndpoint(
                node_id="node-2",
                node_name="Router2",
                adapter_number=0,
                port_number=1
            )
        )
        assert link.link_id == "link-123"
        assert link.node_a.node_id == "node-1"
        assert link.node_b.node_id == "node-2"
        assert link.capturing is False
        assert link.suspend is False

    def test_link_with_capture(self):
        """Test link with packet capture"""
        link = LinkInfo(
            link_id="link-123",
            link_type="ethernet",
            node_a=LinkEndpoint(
                node_id="node-1",
                node_name="Router1",
                adapter_number=0,
                port_number=0
            ),
            node_b=LinkEndpoint(
                node_id="node-2",
                node_name="Router2",
                adapter_number=0,
                port_number=1
            ),
            capturing=True,
            capture_file_name="capture.pcap"
        )
        assert link.capturing is True
        assert link.capture_file_name == "capture.pcap"


# ===== ConnectOperation Tests =====

class TestConnectOperation:
    """Tests for ConnectOperation model"""

    def test_valid_connect_with_adapter_numbers(self):
        """Test connect operation with numeric adapters"""
        op = ConnectOperation(
            action="connect",
            node_a="Router1",
            node_b="Router2",
            port_a=0,
            port_b=1,
            adapter_a=0,
            adapter_b=1
        )
        assert op.action == "connect"
        assert op.node_a == "Router1"
        assert op.adapter_a == 0
        assert op.adapter_b == 1

    def test_valid_connect_with_adapter_names(self):
        """Test connect operation with adapter names"""
        op = ConnectOperation(
            action="connect",
            node_a="Router1",
            node_b="Router2",
            port_a=0,
            port_b=1,
            adapter_a="eth0",
            adapter_b="GigabitEthernet0/0"
        )
        assert op.adapter_a == "eth0"
        assert op.adapter_b == "GigabitEthernet0/0"

    def test_connect_default_adapters(self):
        """Test connect operation with default adapters"""
        op = ConnectOperation(
            action="connect",
            node_a="Router1",
            node_b="Router2",
            port_a=0,
            port_b=1
        )
        assert op.adapter_a == 0
        assert op.adapter_b == 0

    def test_negative_port_fails(self):
        """Test negative port number fails"""
        with pytest.raises(ValidationError) as exc:
            ConnectOperation(
                action="connect",
                node_a="Router1",
                node_b="Router2",
                port_a=-1,
                port_b=0
            )
        assert "port_a" in str(exc.value)


# ===== DisconnectOperation Tests =====

class TestDisconnectOperation:
    """Tests for DisconnectOperation model"""

    def test_valid_disconnect(self):
        """Test valid disconnect operation"""
        op = DisconnectOperation(
            action="disconnect",
            link_id="link-123"
        )
        assert op.action == "disconnect"
        assert op.link_id == "link-123"

    def test_missing_link_id(self):
        """Test disconnect without link_id fails"""
        with pytest.raises(ValidationError) as exc:
            DisconnectOperation(action="disconnect")
        assert "link_id" in str(exc.value)


# ===== CompletedOperation Tests =====

class TestCompletedOperation:
    """Tests for CompletedOperation model"""

    def test_completed_connect(self):
        """Test completed connect operation"""
        op = CompletedOperation(
            index=0,
            action="connect",
            link_id="link-123",
            node_a="Router1",
            node_b="Router2",
            port_a=0,
            port_b=1,
            adapter_a=0,
            adapter_b=0,
            port_a_name="eth0",
            port_b_name="eth1"
        )
        assert op.index == 0
        assert op.action == "connect"
        assert op.link_id == "link-123"
        assert op.port_a_name == "eth0"

    def test_completed_disconnect(self):
        """Test completed disconnect operation"""
        op = CompletedOperation(
            index=1,
            action="disconnect",
            link_id="link-456"
        )
        assert op.index == 1
        assert op.action == "disconnect"
        assert op.node_a is None


# ===== FailedOperation Tests =====

class TestFailedOperation:
    """Tests for FailedOperation model"""

    def test_failed_operation(self):
        """Test failed operation result"""
        op = FailedOperation(
            index=0,
            action="connect",
            operation={"node_a": "Router1", "node_b": "Router2"},
            reason="Node not found"
        )
        assert op.index == 0
        assert op.action == "connect"
        assert op.reason == "Node not found"
        assert "Router1" in op.operation["node_a"]


# ===== OperationResult Tests =====

class TestOperationResult:
    """Tests for OperationResult model"""

    def test_all_success(self):
        """Test result with all operations successful"""
        result = OperationResult(
            completed=[
                CompletedOperation(
                    index=0,
                    action="connect",
                    link_id="link-123"
                ),
                CompletedOperation(
                    index=1,
                    action="disconnect",
                    link_id="link-456"
                )
            ],
            failed=None
        )
        assert len(result.completed) == 2
        assert result.failed is None

    def test_with_failure(self):
        """Test result with one failure"""
        result = OperationResult(
            completed=[
                CompletedOperation(index=0, action="connect", link_id="link-123")
            ],
            failed=FailedOperation(
                index=1,
                action="disconnect",
                operation={"link_id": "link-456"},
                reason="Link not found"
            )
        )
        assert len(result.completed) == 1
        assert result.failed is not None
        assert result.failed.reason == "Link not found"


# ===== TemplateInfo Tests =====

class TestTemplateInfo:
    """Tests for TemplateInfo model"""

    def test_valid_template(self):
        """Test valid template"""
        template = TemplateInfo(
            template_id="tmpl-123",
            name="Ethernet switch",
            category="switch",
            node_type="ethernet_switch",
            builtin=True
        )
        assert template.template_id == "tmpl-123"
        assert template.name == "Ethernet switch"
        assert template.builtin is True

    def test_template_defaults(self):
        """Test template default values"""
        template = TemplateInfo(
            template_id="tmpl-123",
            name="Custom Device",
            category="guest"
        )
        assert template.compute_id == "local"
        assert template.builtin is False


# ===== DrawingInfo Tests =====

class TestDrawingInfo:
    """Tests for DrawingInfo model"""

    def test_valid_drawing(self):
        """Test valid drawing"""
        drawing = DrawingInfo(
            drawing_id="draw-123",
            project_id="proj-123",
            x=100,
            y=200,
            z=1,
            svg="<rect/>"
        )
        assert drawing.drawing_id == "draw-123"
        assert drawing.x == 100
        assert drawing.y == 200
        assert drawing.z == 1

    def test_drawing_defaults(self):
        """Test drawing default values"""
        drawing = DrawingInfo(
            drawing_id="draw-123",
            project_id="proj-123",
            x=100,
            y=200,
            svg="<rect/>"
        )
        assert drawing.z == 0
        assert drawing.rotation == 0
        assert drawing.locked is False


# ===== ConsoleStatus Tests =====

class TestConsoleStatus:
    """Tests for ConsoleStatus model"""

    def test_connected_status(self):
        """Test connected console status"""
        status = ConsoleStatus(
            connected=True,
            node_name="Router1",
            session_id="sess-123",
            host="192.168.1.20",
            port=5000,
            buffer_size=1024,
            created_at="2025-10-23T10:30:00"
        )
        assert status.connected is True
        assert status.node_name == "Router1"
        assert status.port == 5000

    def test_disconnected_status(self):
        """Test disconnected console status"""
        status = ConsoleStatus(
            connected=False,
            node_name="Router1"
        )
        assert status.connected is False
        assert status.session_id is None
        assert status.port is None


# ===== ErrorResponse Tests =====

class TestErrorResponse:
    """Tests for ErrorResponse model"""

    def test_simple_error(self):
        """Test simple error response"""
        error = ErrorResponse(
            error="Node not found",
            details="Node 'Router1' does not exist"
        )
        assert error.error == "Node not found"
        assert error.details == "Node 'Router1' does not exist"

    def test_error_with_suggested_action(self):
        """Test error with suggested action"""
        error = ErrorResponse(
            error="Validation failed",
            details="Port already in use",
            suggested_action="Use get_links() to check current connections",
            field="port_a",
            operation_index=0
        )
        assert error.suggested_action == "Use get_links() to check current connections"
        assert error.field == "port_a"
        assert error.operation_index == 0


# ===== validate_connection_operations Tests =====

class TestValidateConnectionOperations:
    """Tests for validate_connection_operations helper"""

    def test_valid_operations(self):
        """Test validation of valid operations"""
        ops = [
            {
                "action": "connect",
                "node_a": "Router1",
                "node_b": "Router2",
                "port_a": 0,
                "port_b": 1
            },
            {
                "action": "disconnect",
                "link_id": "link-123"
            }
        ]
        parsed, error = validate_connection_operations(ops)
        assert error is None
        assert len(parsed) == 2
        assert isinstance(parsed[0], ConnectOperation)
        assert isinstance(parsed[1], DisconnectOperation)

    def test_invalid_action(self):
        """Test validation with invalid action"""
        ops = [
            {
                "action": "invalid",
                "link_id": "link-123"
            }
        ]
        parsed, error = validate_connection_operations(ops)
        assert error is not None
        assert "Invalid action" in error
        assert "invalid" in error
        assert len(parsed) == 0

    def test_missing_fields(self):
        """Test validation with missing required fields"""
        ops = [
            {
                "action": "connect",
                "node_a": "Router1"
                # Missing node_b, port_a, port_b
            }
        ]
        parsed, error = validate_connection_operations(ops)
        assert error is not None
        assert "Validation error" in error
        assert len(parsed) == 0

    def test_empty_operations(self):
        """Test validation with empty list"""
        parsed, error = validate_connection_operations([])
        assert error is None
        assert len(parsed) == 0

    def test_uppercase_action_fails(self):
        """Test uppercase action fails (Literal is case-sensitive)"""
        ops = [
            {
                "action": "CONNECT",
                "node_a": "Router1",
                "node_b": "Router2",
                "port_a": 0,
                "port_b": 1
            }
        ]
        parsed, error = validate_connection_operations(ops)
        # Pydantic Literal type is case-sensitive, so uppercase fails
        assert error is not None
        assert "Validation error" in error
        assert len(parsed) == 0
