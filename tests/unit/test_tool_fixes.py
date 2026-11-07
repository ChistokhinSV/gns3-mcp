"""Regression tests for tool-level fixes (GM-86, GM-88, GM-89)

GNS3 API calls are mocked; behaviour against a live server was checked in the lab.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from tools import console_tools
from tools.link_tools import set_connection_impl
from tools.node_tools import _set_single_node_impl, create_node_impl, set_node_impl

# ===== GM-86: node create/set properties =====


def _qemu_node(**props):
    return {
        "node_id": "n-1",
        "name": "ops1",
        "node_type": "qemu",
        "status": "stopped",
        "console_type": "telnet",
        "console": 5000,
        "properties": {
            "ram": 1024,
            "cpus": 1,
            "adapters": 1,
            "hda_disk_image": "template.qcow2",
            "cdrom_image": "",
            "options": "",
            **props,
        },
    }


def _gns3_echoing_put():
    """GNS3 client mock whose PUT applies known QEMU properties and drops unknown ones"""
    gns3 = AsyncMock()
    gns3.get_templates.return_value = [{"name": "Ubuntu Cloud Guest", "template_id": "t-1"}]
    gns3.create_node_from_template.return_value = _qemu_node()

    async def put(project_id, node_id, payload):
        node = _qemu_node()
        known = node["properties"]
        node["properties"].update(
            {k: v for k, v in payload.get("properties", {}).items() if k in known}
        )
        node.update({k: v for k, v in payload.items() if k != "properties"})
        return node

    gns3.update_node.side_effect = put
    return gns3


class TestNodeCreateProperties:
    @pytest.mark.asyncio
    async def test_create_applies_properties_with_follow_up_put(self):
        gns3 = _gns3_echoing_put()
        props = {
            "ram": 12288,
            "cpus": 6,
            "adapters": 2,
            "hda_disk_image": "ops1-60G.qcow2",
            "cdrom_image": "ops1-seed.iso",
        }

        result = json.loads(
            await create_node_impl(gns3, "p-1", "Ubuntu Cloud Guest", 0, 0, "ops1", "local", props)
        )

        # Template endpoint gets no overrides (API ignores them); PUT carries them nested
        template_payload = gns3.create_node_from_template.call_args.args[2]
        assert "properties" not in template_payload
        put_payload = gns3.update_node.call_args.args[2]
        assert put_payload == {"properties": props}
        assert result["message"] == "Node created successfully"
        assert sorted(result["applied_properties"]) == sorted(props)
        assert "unapplied_properties" not in result

    @pytest.mark.asyncio
    async def test_create_reports_unapplied_properties(self):
        gns3 = _gns3_echoing_put()

        result = json.loads(
            await create_node_impl(
                gns3, "p-1", "Ubuntu Cloud Guest", 0, 0, "ops1", "local", {"ram": 2048, "bogus": 1}
            )
        )

        assert "not applied" in result["message"]
        assert list(result["unapplied_properties"]) == ["bogus"]
        assert result["applied_properties"] == ["ram"]

    @pytest.mark.asyncio
    async def test_create_sends_top_level_fields_top_level(self):
        gns3 = _gns3_echoing_put()

        await create_node_impl(
            gns3, "p-1", "Ubuntu Cloud Guest", 0, 0, None, "local", {"console_type": "vnc"}
        )

        assert gns3.update_node.call_args.args[2] == {"console_type": "vnc"}

    @pytest.mark.asyncio
    async def test_create_property_put_failure_is_loud(self):
        gns3 = _gns3_echoing_put()
        gns3.update_node.side_effect = RuntimeError("image not found")

        result = json.loads(
            await create_node_impl(
                gns3, "p-1", "Ubuntu Cloud Guest", 0, 0, "ops1", "local", {"hda_disk_image": "x"}
            )
        )

        assert "created, but properties were not applied" in result["error"]
        assert "image not found" in result["details"]


# ===== GM-98: create from a template with big images times out =====


def _windows_node(**overrides):
    node = {
        "node_id": "n-9",
        "name": "Windows10-1",
        "node_type": "qemu",
        "status": "stopped",
        "template_id": "t-win",
        "x": 0,
        "y": 0,
        "label": {"text": "Windows10-1"},
    }
    return {**node, **overrides}


def _gns3_slow_create(*nodes_after):
    """POST times out; node list is empty before it and `nodes_after` on every poll"""
    import httpx

    gns3 = AsyncMock()
    gns3.get_templates.return_value = [{"name": "Windows10", "template_id": "t-win"}]
    gns3.create_node_from_template.side_effect = httpx.ReadTimeout("GNS3 server did not answer")
    polls = iter([[]])
    gns3.get_nodes.side_effect = lambda project_id: next(polls, list(nodes_after))
    return gns3


@pytest.fixture
def fast_recovery(monkeypatch):
    from tools import node_tools

    monkeypatch.setattr(node_tools, "_LATE_NODE_POLL_INTERVAL", 0.01)
    monkeypatch.setenv("GNS3_NODE_CREATE_RECOVERY_WAIT", "0.05")


class TestNodeCreateTimeout:
    async def _create(self, gns3):
        return json.loads(
            await create_node_impl(gns3, "p-1", "Windows10", -290, 210, "ADMIN-PC", "local")
        )

    @pytest.mark.asyncio
    async def test_late_node_is_named_and_placed(self, fast_recovery):
        gns3 = _gns3_slow_create(_windows_node())

        result = await self._create(gns3)

        gns3.update_node.assert_awaited_once_with(
            "p-1", "n-9", {"name": "ADMIN-PC", "x": -290, "y": 210}
        )
        assert result["node"]["name"] == "ADMIN-PC"
        assert "took longer than 180s" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_create_uses_long_timeout(self, fast_recovery, monkeypatch):
        monkeypatch.setenv("GNS3_NODE_CREATE_TIMEOUT", "600")
        gns3 = _gns3_slow_create(_windows_node())

        await self._create(gns3)

        assert gns3.create_node_from_template.call_args.kwargs["timeout"] == 600

    @pytest.mark.asyncio
    async def test_no_node_yet_says_do_not_retry(self, fast_recovery):
        gns3 = _gns3_slow_create()

        result = await self._create(gns3)

        assert result["error_code"] == "TIMEOUT"
        assert result["details"] == "GNS3 server did not answer"
        assert "Do not call create again" in result["suggested_action"]
        assert "name='ADMIN-PC', x=-290, y=210" in result["suggested_action"]
        gns3.update_node.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_two_new_nodes_are_not_guessed(self, fast_recovery):
        gns3 = _gns3_slow_create(_windows_node(), _windows_node(node_id="n-10", name="Windows10-2"))

        result = await self._create(gns3)

        assert result["error_code"] == "TIMEOUT"
        assert result["context"]["new_nodes"] == ["Windows10-1", "Windows10-2"]
        gns3.update_node.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_gateway_timeout_is_treated_as_late(self, fast_recovery):
        import httpx

        gns3 = _gns3_slow_create(_windows_node())
        request = httpx.Request("POST", "http://gns3/v3/projects/p-1/templates/t-win")
        gns3.create_node_from_template.side_effect = httpx.HTTPStatusError(
            "504", request=request, response=httpx.Response(504, request=request)
        )

        result = await self._create(gns3)

        assert result["node"]["name"] == "ADMIN-PC"

    @pytest.mark.asyncio
    async def test_connect_timeout_is_not_waited_for(self, fast_recovery):
        import httpx

        gns3 = _gns3_slow_create(_windows_node())
        gns3.create_node_from_template.side_effect = httpx.ConnectTimeout("no connection")

        result = await self._create(gns3)

        assert result["error_code"] == "OPERATION_FAILED"
        assert result["details"] == "no connection"
        assert gns3.get_nodes.call_count == 1

    @pytest.mark.asyncio
    async def test_real_error_is_not_retried(self, fast_recovery):
        import httpx

        gns3 = _gns3_slow_create(_windows_node())
        request = httpx.Request("POST", "http://gns3/v3/projects/p-1/templates/t-win")
        gns3.create_node_from_template.side_effect = httpx.HTTPStatusError(
            "409",
            request=request,
            response=httpx.Response(409, json={"message": "Image missing"}, request=request),
        )

        result = await self._create(gns3)

        assert result["error_code"] == "OPERATION_FAILED"
        assert result["details"] == "Image missing"
        assert gns3.get_nodes.call_count == 1  # only the snapshot before the POST

    @pytest.mark.asyncio
    async def test_fast_create_places_node_only_when_needed(self):
        gns3 = AsyncMock()
        gns3.get_templates.return_value = [{"name": "Windows10", "template_id": "t-win"}]
        gns3.get_nodes.return_value = []
        gns3.create_node_from_template.return_value = _windows_node(x=-290, y=210)

        result = await self._create(gns3)

        # name ignored by the template endpoint -> renamed; x/y already right -> not sent
        gns3.update_node.assert_awaited_once_with("p-1", "n-9", {"name": "ADMIN-PC"})
        assert "warnings" not in result


class TestNodeSetProperties:
    @pytest.mark.asyncio
    async def test_set_disk_cdrom_options_nested_for_qemu(self):
        gns3 = _gns3_echoing_put()
        props = {"hda_disk_image": "big.qcow2", "cdrom_image": "seed.iso", "options": "-cpu host"}

        results = await _set_single_node_impl(gns3, "p-1", _qemu_node(), ram=4096, properties=props)

        payload = gns3.update_node.call_args.args[2]
        assert payload == {"properties": {**props, "ram": 4096}}
        assert results[0].startswith("Updated:")
        assert not any(r.startswith("Warning") for r in results)

    @pytest.mark.asyncio
    async def test_set_warns_on_dropped_property(self):
        gns3 = _gns3_echoing_put()

        results = await _set_single_node_impl(
            gns3, "p-1", _qemu_node(), properties={"no_such_prop": True}
        )

        assert any("not applied" in r and "no_such_prop" in r for r in results)

    @pytest.mark.asyncio
    async def test_set_console_type_is_top_level(self):
        """console_type nested under properties was silently dropped for QEMU"""
        gns3 = _gns3_echoing_put()

        results = await _set_single_node_impl(gns3, "p-1", _qemu_node(), console_type="vnc")

        assert gns3.update_node.call_args.args[2] == {"console_type": "vnc"}
        assert not any(r.startswith("Warning") for r in results)

    @pytest.mark.asyncio
    async def test_set_switch_ports_nested_and_keeps_existing_ports(self):
        """ports_mapping sent top-level was silently dropped; existing VLANs must survive"""
        existing = [
            {"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 10 + i}
            for i in range(8)
        ]
        switch = {
            "node_id": "sw-1",
            "name": "SW",
            "node_type": "ethernet_switch",
            "status": "started",
            "properties": {"ports_mapping": existing},
        }
        gns3 = AsyncMock()

        async def put(project_id, node_id, payload):
            return {**switch, "properties": payload["properties"]}

        gns3.update_node.side_effect = put

        results = await _set_single_node_impl(gns3, "p-1", switch, ports=10)

        mapping = gns3.update_node.call_args.args[2]["properties"]["ports_mapping"]
        assert len(mapping) == 10
        assert mapping[:8] == existing
        assert mapping[9] == {"name": "Ethernet9", "port_number": 9, "type": "access", "vlan": 1}
        assert not any(r.startswith("Warning") for r in results)

    @pytest.mark.asyncio
    async def test_set_error_surfaces_gns3_message(self):
        """A 409 must carry GNS3's reason (e.g. missing image), not just the status line"""
        gns3 = _gns3_echoing_put()
        gns3.get_nodes.return_value = [_qemu_node()]
        response = MagicMock()
        response.json.return_value = {"message": "The image 'x.qcow2' is missing"}
        error = RuntimeError("Client error '409 Conflict'")
        error.response = response
        gns3.update_node.side_effect = error

        result = json.loads(
            await set_node_impl(gns3, "p-1", "ops1", properties={"hda_disk_image": "x.qcow2"})
        )

        assert result["details"] == "The image 'x.qcow2' is missing"


# ===== GM-88: link batch port names =====


class TestLinkBatchPortNames:
    @pytest.mark.asyncio
    async def test_switch_port_name_follows_port_number(self):
        nodes = [
            {
                "node_id": "fw",
                "name": "FGT-SITE002",
                "ports": [{"adapter_number": 0, "port_number": 0, "name": "port1"}],
            },
            {
                "node_id": "sw",
                "name": "SW-MGMT",
                "ports": [
                    {"adapter_number": 0, "port_number": i, "name": f"Ethernet{i}"}
                    for i in range(8)
                ],
            },
        ]
        gns3 = AsyncMock()
        gns3.get_nodes.return_value = nodes
        gns3.get_links.return_value = []
        gns3.create_link.return_value = {"link_id": "l-1"}

        result = json.loads(
            await set_connection_impl(
                gns3,
                "p-1",
                [
                    {
                        "action": "connect",
                        "node_a": "FGT-SITE002",
                        "node_b": "SW-MGMT",
                        "adapter_a": 0,
                        "port_a": 0,
                        "adapter_b": 0,
                        "port_b": 2,
                    }
                ],
            )
        )

        done = result["completed"][0]
        assert (done["port_b"], done["port_b_name"]) == (2, "Ethernet2")
        assert done["port_a_name"] == "port1"

    @pytest.mark.asyncio
    async def test_named_adapter_drives_link_port_number(self):
        nodes = [
            {
                "node_id": "r",
                "name": "R1",
                "ports": [{"adapter_number": 0, "port_number": 0, "name": "eth0"}],
            },
            {
                "node_id": "sw",
                "name": "SW",
                "ports": [
                    {"adapter_number": 0, "port_number": i, "name": f"Ethernet{i}"}
                    for i in range(4)
                ],
            },
        ]
        gns3 = AsyncMock()
        gns3.get_nodes.return_value = nodes
        gns3.get_links.return_value = []
        gns3.create_link.return_value = {"link_id": "l-1"}

        await set_connection_impl(
            gns3,
            "p-1",
            [
                {
                    "action": "connect",
                    "node_a": "R1",
                    "node_b": "SW",
                    "adapter_a": "eth0",
                    "port_a": 0,
                    "adapter_b": "Ethernet3",
                    "port_b": 0,
                }
            ],
        )

        link_spec = gns3.create_link.call_args.args[1]
        assert link_spec["nodes"][1] == {"node_id": "sw", "adapter_number": 0, "port_number": 3}


# ===== GM-89: console batch send_and_wait wait-only =====


class TestConsoleBatchWaitOnly:
    @pytest.mark.asyncio
    async def test_send_and_wait_without_command(self, monkeypatch):
        app = MagicMock()
        app.console.has_accessed_terminal_by_node.return_value = True
        impl = AsyncMock(
            return_value=json.dumps({"output": "login:", "pattern_found": True, "wait_only": True})
        )
        monkeypatch.setattr(console_tools, "send_and_wait_console_impl", impl)

        result = json.loads(
            await console_tools.console_batch_impl(
                app,
                [
                    {
                        "type": "send_and_wait",
                        "node_name": "ops1",
                        "wait_pattern": "login:",
                        "timeout": 15,
                    }
                ],
            )
        )

        assert impl.call_args.args[2] is None  # command
        assert impl.call_args.args[3] == "login:"
        assert result["results"][0]["success"] is True
