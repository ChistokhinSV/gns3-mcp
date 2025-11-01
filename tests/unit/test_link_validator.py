"""Unit tests for LinkValidator (link_validator.py)

Tests two-phase validation logic for network topology changes.
"""

import pytest
from link_validator import LinkValidator

# ===== Test Data Fixtures =====


@pytest.fixture
def sample_nodes():
    """Sample nodes with port information"""
    return [
        {
            "node_id": "node-1",
            "name": "Router1",
            "node_type": "qemu",
            "ports": [
                {"adapter_number": 0, "port_number": 0, "name": "eth0"},
                {"adapter_number": 0, "port_number": 1, "name": "eth1"},
                {"adapter_number": 1, "port_number": 0, "name": "GigabitEthernet0/0"},
            ],
        },
        {
            "node_id": "node-2",
            "name": "Router2",
            "node_type": "qemu",
            "ports": [
                {"adapter_number": 0, "port_number": 0, "name": "eth0"},
                {"adapter_number": 0, "port_number": 1, "name": "eth1"},
            ],
        },
        {
            "node_id": "node-3",
            "name": "Switch1",
            "node_type": "ethernet_switch",
            # No ports info (some node types don't expose this)
        },
    ]


@pytest.fixture
def sample_links():
    """Sample links showing existing connections"""
    return [
        {
            "link_id": "link-1",
            "nodes": [
                {"node_id": "node-1", "adapter_number": 0, "port_number": 0},
                {"node_id": "node-2", "adapter_number": 0, "port_number": 0},
            ],
        }
    ]


@pytest.fixture
def validator(sample_nodes, sample_links):
    """LinkValidator instance with sample data"""
    return LinkValidator(sample_nodes, sample_links)


# ===== Initialization Tests =====


class TestLinkValidatorInit:
    """Tests for LinkValidator initialization"""

    def test_init_builds_node_maps(self, validator):
        """Test initialization builds node lookup maps"""
        assert "Router1" in validator.nodes
        assert "Router2" in validator.nodes
        assert "node-1" in validator.node_ids

    def test_init_builds_link_map(self, validator):
        """Test initialization builds link lookup map"""
        assert "link-1" in validator.link_ids

    def test_init_builds_port_usage(self, validator):
        """Test initialization builds port usage map"""
        # Port node-1:0:0 should be in use
        assert "node-1" in validator.port_usage
        assert 0 in validator.port_usage["node-1"]
        assert 0 in validator.port_usage["node-1"][0]

    def test_init_empty_nodes_and_links(self):
        """Test initialization with empty data"""
        validator = LinkValidator([], [])
        assert len(validator.nodes) == 0
        assert len(validator.links) == 0
        assert len(validator.port_usage) == 0


# ===== Port Usage Map Tests =====


class TestPortUsageMap:
    """Tests for _build_port_usage_map"""

    def test_port_usage_detects_connected_ports(self, validator):
        """Test port usage map shows connected ports"""
        # Router1 eth0 (adapter 0, port 0) is connected
        assert validator._is_port_used("node-1", 0, 0) is True
        # Router2 eth0 (adapter 0, port 0) is connected
        assert validator._is_port_used("node-2", 0, 0) is True

    def test_port_usage_shows_free_ports(self, validator):
        """Test port usage map shows free ports"""
        # Router1 eth1 (adapter 0, port 1) is free
        assert validator._is_port_used("node-1", 0, 1) is False
        # Router2 eth1 (adapter 0, port 1) is free
        assert validator._is_port_used("node-2", 0, 1) is False

    def test_port_usage_with_multiple_adapters(self, validator):
        """Test port usage across multiple adapters"""
        # Router1 GigabitEthernet0/0 (adapter 1, port 0) is free
        assert validator._is_port_used("node-1", 1, 0) is False


# ===== Adapter Name Resolution Tests =====


class TestAdapterNameResolution:
    """Tests for adapter name mapping and resolution"""

    def test_adapter_name_map_built(self, validator):
        """Test adapter name maps are built correctly"""
        assert "Router1" in validator.adapter_names
        assert (0, 0) in validator.adapter_names["Router1"]
        assert validator.adapter_names["Router1"][(0, 0)] == "eth0"

    def test_resolve_numeric_adapter(self, validator):
        """Test resolving numeric adapter identifier"""
        adapter, port, name, error = validator.resolve_adapter_identifier("Router1", 0)
        assert error is None
        assert adapter == 0
        assert port == 0
        assert "eth0" in name or "adapter0" in name

    def test_resolve_adapter_name(self, validator):
        """Test resolving adapter by name"""
        adapter, port, name, error = validator.resolve_adapter_identifier("Router1", "eth0")
        assert error is None
        assert adapter == 0
        assert port == 0
        assert name == "eth0"

    def test_resolve_adapter_name_case_sensitive(self, validator):
        """Test adapter name resolution is case-sensitive"""
        adapter, port, name, error = validator.resolve_adapter_identifier("Router1", "ETH0")
        assert error is not None
        assert "not found" in error
        assert "case-sensitive" in error

    def test_resolve_adapter_invalid_node(self, validator):
        """Test resolving adapter on non-existent node"""
        adapter, port, name, error = validator.resolve_adapter_identifier("InvalidNode", 0)
        assert error is not None
        assert "not found" in error

    def test_resolve_adapter_no_port_info(self, validator):
        """Test resolving adapter name on node without port info"""
        adapter, port, name, error = validator.resolve_adapter_identifier("Switch1", "eth0")
        assert error is not None
        assert "no port information" in error

    def test_resolve_adapter_nonexistent_name(self, validator):
        """Test resolving non-existent adapter name shows available ports"""
        adapter, port, name, error = validator.resolve_adapter_identifier("Router1", "eth99")
        assert error is not None
        assert "not found" in error
        assert "Available ports" in error
        assert "eth0" in error or "eth1" in error


# ===== Connect Validation Tests =====


class TestValidateConnect:
    """Tests for validate_connect"""

    def test_valid_connect(self, validator):
        """Test validating a valid connection"""
        error = validator.validate_connect(
            "Router1",
            "Router2",
            port_a=1,
            port_b=1,  # Both eth1, currently free
            adapter_a=0,
            adapter_b=0,
        )
        assert error is None

    def test_connect_node_not_found(self, validator):
        """Test connecting non-existent node"""
        error = validator.validate_connect("InvalidNode", "Router2", port_a=0, port_b=1)
        assert error is not None
        assert "InvalidNode" in error
        assert "not found" in error

    def test_connect_port_in_use(self, validator):
        """Test connecting to already-used port"""
        error = validator.validate_connect(
            "Router1",
            "Router2",
            port_a=0,
            port_b=1,  # Router1 eth0 already connected
            adapter_a=0,
            adapter_b=0,
        )
        assert error is not None
        assert "already connected" in error
        assert "link-1" in error

    def test_connect_port_doesnt_exist(self, validator):
        """Test connecting to non-existent port"""
        error = validator.validate_connect(
            "Router1",
            "Router2",
            port_a=99,
            port_b=1,  # Port 99 doesn't exist
            adapter_a=0,
            adapter_b=0,
        )
        assert error is not None
        assert "no port" in error
        assert "99" in error

    def test_connect_node_without_port_info(self, validator):
        """Test connecting node without port information (should succeed)"""
        # Switch1 has no port info, validation should skip
        error = validator.validate_connect(
            "Switch1", "Router1", port_a=0, port_b=1, adapter_a=0, adapter_b=0
        )
        assert error is None  # No error since Switch1 has no port validation


# ===== Disconnect Validation Tests =====


class TestValidateDisconnect:
    """Tests for validate_disconnect"""

    def test_valid_disconnect(self, validator):
        """Test validating a valid disconnect"""
        error = validator.validate_disconnect("link-1")
        assert error is None

    def test_disconnect_invalid_link(self, validator):
        """Test disconnecting non-existent link"""
        error = validator.validate_disconnect("invalid-link-id")
        assert error is not None
        assert "not found" in error
        assert "invalid-link-id" in error


# ===== Port Availability Tests =====


class TestCheckPortAvailable:
    """Tests for _check_port_available"""

    def test_check_available_port(self, validator):
        """Test checking a free port"""
        error = validator._check_port_available("node-1", "Router1", 0, 1)
        assert error is None

    def test_check_used_port(self, validator):
        """Test checking a port in use"""
        error = validator._check_port_available("node-1", "Router1", 0, 0)
        assert error is not None
        assert "already connected" in error
        assert "link-1" in error

    def test_check_port_on_unused_node(self, validator):
        """Test checking port on node with no connections"""
        # node-3 (Switch1) has no links
        error = validator._check_port_available("node-3", "Switch1", 0, 0)
        assert error is None


# ===== Find Link Using Port Tests =====


class TestFindLinkUsingPort:
    """Tests for _find_link_using_port"""

    def test_find_existing_link(self, validator):
        """Test finding link that uses a port"""
        link_id = validator._find_link_using_port("node-1", 0, 0)
        assert link_id == "link-1"

    def test_find_link_unused_port(self, validator):
        """Test finding link for unused port returns 'unknown'"""
        link_id = validator._find_link_using_port("node-1", 0, 1)
        assert link_id == "unknown"


# ===== Port Exists Validation Tests =====


class TestValidatePortExists:
    """Tests for _validate_port_exists"""

    def test_valid_port(self, validator):
        """Test validating existing port"""
        node = validator.nodes["Router1"]
        error = validator._validate_port_exists(node, 0, 0, "Router1")
        assert error is None

    def test_invalid_port(self, validator):
        """Test validating non-existent port"""
        node = validator.nodes["Router1"]
        error = validator._validate_port_exists(node, 0, 99, "Router1")
        assert error is not None
        assert "no port" in error
        assert "adapter 0" in error

    def test_node_without_port_info(self, validator):
        """Test validating port on node without port info"""
        node = validator.nodes["Switch1"]
        error = validator._validate_port_exists(node, 0, 0, "Switch1")
        assert error is None  # Should pass when no port info available

    def test_empty_ports_list(self, sample_nodes):
        """Test validating port when ports list is empty"""
        nodes = [{"node_id": "node-empty", "name": "EmptyNode", "ports": []}]
        validator = LinkValidator(nodes, [])
        node = validator.nodes["EmptyNode"]
        error = validator._validate_port_exists(node, 0, 0, "EmptyNode")
        assert error is None  # Should pass when ports list is empty


# ===== Get Port Info Tests =====


class TestGetPortInfo:
    """Tests for get_port_info"""

    def test_get_port_info_with_ports(self, validator):
        """Test getting port info for node with ports"""
        info = validator.get_port_info("Router1")
        assert info is not None
        assert "Router1" in info
        assert "eth0" in info
        assert "eth1" in info
        assert "in use" in info  # eth0 is in use
        assert "free" in info  # eth1 is free

    def test_get_port_info_without_ports(self, validator):
        """Test getting port info for node without port information"""
        info = validator.get_port_info("Switch1")
        assert info is not None
        assert "no port information" in info

    def test_get_port_info_invalid_node(self, validator):
        """Test getting port info for non-existent node"""
        info = validator.get_port_info("InvalidNode")
        assert info is None


# ===== Edge Cases Tests =====


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_multiple_links_same_node(self):
        """Test validator with multiple links on same node"""
        nodes = [
            {
                "node_id": "node-1",
                "name": "Router1",
                "ports": [
                    {"adapter_number": 0, "port_number": 0, "name": "eth0"},
                    {"adapter_number": 0, "port_number": 1, "name": "eth1"},
                    {"adapter_number": 0, "port_number": 2, "name": "eth2"},
                ],
            },
            {"node_id": "node-2", "name": "Router2", "ports": []},
            {"node_id": "node-3", "name": "Router3", "ports": []},
        ]
        links = [
            {
                "link_id": "link-1",
                "nodes": [
                    {"node_id": "node-1", "adapter_number": 0, "port_number": 0},
                    {"node_id": "node-2", "adapter_number": 0, "port_number": 0},
                ],
            },
            {
                "link_id": "link-2",
                "nodes": [
                    {"node_id": "node-1", "adapter_number": 0, "port_number": 1},
                    {"node_id": "node-3", "adapter_number": 0, "port_number": 0},
                ],
            },
        ]
        validator = LinkValidator(nodes, links)

        # Port 0 and 1 should be in use, port 2 should be free
        assert validator._is_port_used("node-1", 0, 0) is True
        assert validator._is_port_used("node-1", 0, 1) is True
        assert validator._is_port_used("node-1", 0, 2) is False

    def test_adapter_name_truncation_long_list(self):
        """Test adapter name error message truncates long port lists"""
        nodes = [
            {
                "node_id": "node-1",
                "name": "BigSwitch",
                "ports": [
                    {"adapter_number": 0, "port_number": i, "name": f"port{i}"} for i in range(20)
                ],
            }
        ]
        validator = LinkValidator(nodes, [])

        # Try to resolve non-existent port - should show truncated list
        adapter, port, name, error = validator.resolve_adapter_identifier("BigSwitch", "port99")
        assert error is not None
        assert "20 total" in error  # Should mention total count
        assert "..." in error  # Should have truncation indicator

    def test_link_with_missing_node_fields(self):
        """Test handling links with missing node fields"""
        nodes = [
            {"node_id": "node-1", "name": "Router1", "ports": []},
            {"node_id": "node-2", "name": "Router2", "ports": []},
        ]
        links = [
            {
                "link_id": "link-incomplete",
                "nodes": [
                    {"node_id": "node-1"},  # Missing adapter_number, port_number
                    {"node_id": "node-2", "adapter_number": 0},  # Missing port_number
                ],
            }
        ]
        validator = LinkValidator(nodes, links)

        # Should handle gracefully without crashing
        assert "node-1" in validator.node_ids

    def test_resolve_adapter_invalid_type(self, validator):
        """Test resolving adapter with invalid type (not int or str)"""
        adapter, port, name, error = validator.resolve_adapter_identifier("Router1", [])
        assert error is not None
        assert "Invalid adapter identifier type" in error
