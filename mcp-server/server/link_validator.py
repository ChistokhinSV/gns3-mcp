"""Link Operation Validator

Two-phase validation for network topology changes:
1. Validate all operations (check nodes exist, ports free, etc.)
2. Execute operations (only if all valid)

This prevents partial topology changes that leave the network in an inconsistent state.
"""

from typing import Dict, List, Set, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LinkValidator:
    """Validates link operations before execution"""

    def __init__(self, nodes: List[Dict], links: List[Dict]):
        """Initialize validator with current topology state

        Args:
            nodes: List of node dictionaries from GNS3 API
            links: List of link dictionaries from GNS3 API
        """
        self.nodes = {n['name']: n for n in nodes}
        self.node_ids = {n['node_id']: n for n in nodes}
        self.links = links
        self.link_ids = {link['link_id']: link for link in links}
        self.port_usage = self._build_port_usage_map()

    def _build_port_usage_map(self) -> Dict[str, Dict[int, Set[int]]]:
        """Build map of currently used ports

        Returns:
            Nested dict: {node_id: {adapter_number: {port_numbers}}}
        """
        usage = {}

        for link in self.links:
            link_nodes = link.get('nodes', [])
            for node in link_nodes:
                node_id = node.get('node_id')
                adapter = node.get('adapter_number', 0)
                port = node.get('port_number')

                if not node_id or port is None:
                    continue

                if node_id not in usage:
                    usage[node_id] = {}
                if adapter not in usage[node_id]:
                    usage[node_id][adapter] = set()

                usage[node_id][adapter].add(port)

        logger.debug(f"Built port usage map: {usage}")
        return usage

    def validate_connect(self,
                        node_a_name: str,
                        node_b_name: str,
                        port_a: int,
                        port_b: int,
                        adapter_a: int = 0,
                        adapter_b: int = 0) -> Optional[str]:
        """Validate a connect operation

        Args:
            node_a_name: Name of first node
            node_b_name: Name of second node
            port_a: Port number on node A
            port_b: Port number on node B
            adapter_a: Adapter number on node A
            adapter_b: Adapter number on node B

        Returns:
            Error message if invalid, None if valid
        """
        # Check nodes exist
        if node_a_name not in self.nodes:
            return f"Node '{node_a_name}' not found in project"

        if node_b_name not in self.nodes:
            return f"Node '{node_b_name}' not found in project"

        node_a = self.nodes[node_a_name]
        node_b = self.nodes[node_b_name]

        # Check ports are available
        error = self._check_port_available(
            node_a['node_id'], node_a_name, adapter_a, port_a
        )
        if error:
            return error

        error = self._check_port_available(
            node_b['node_id'], node_b_name, adapter_b, port_b
        )
        if error:
            return error

        # Validate adapter/port exists on device
        error = self._validate_port_exists(node_a, adapter_a, port_a, node_a_name)
        if error:
            return error

        error = self._validate_port_exists(node_b, adapter_b, port_b, node_b_name)
        if error:
            return error

        return None

    def validate_disconnect(self, link_id: str) -> Optional[str]:
        """Validate a disconnect operation

        Args:
            link_id: Link ID to disconnect

        Returns:
            Error message if invalid, None if valid
        """
        if link_id not in self.link_ids:
            return f"Link '{link_id}' not found in project"

        return None

    def _check_port_available(self,
                              node_id: str,
                              node_name: str,
                              adapter: int,
                              port: int) -> Optional[str]:
        """Check if a port is currently available (not in use)

        Args:
            node_id: Node ID
            node_name: Node name (for error messages)
            adapter: Adapter number
            port: Port number

        Returns:
            Error message if port is in use, None if available
        """
        if node_id in self.port_usage:
            if adapter in self.port_usage[node_id]:
                if port in self.port_usage[node_id][adapter]:
                    # Find which link is using this port
                    link_id = self._find_link_using_port(node_id, adapter, port)
                    return (
                        f"Port {node_name} adapter {adapter} port {port} is already connected "
                        f"(link: {link_id}). Use get_links() to see current topology, then disconnect "
                        f"with set_connection([{{'action': 'disconnect', 'link_id': '{link_id}'}}])"
                    )

        return None

    def _find_link_using_port(self, node_id: str, adapter: int, port: int) -> Optional[str]:
        """Find link ID that uses specified port

        Args:
            node_id: Node ID
            adapter: Adapter number
            port: Port number

        Returns:
            Link ID or "unknown" if not found
        """
        for link in self.links:
            for node in link.get('nodes', []):
                if (node.get('node_id') == node_id and
                    node.get('adapter_number', 0) == adapter and
                    node.get('port_number') == port):
                    return link['link_id']

        return "unknown"

    def _validate_port_exists(self,
                             node: Dict,
                             adapter: int,
                             port: int,
                             node_name: str) -> Optional[str]:
        """Validate that adapter/port actually exists on the node

        Args:
            node: Node dictionary from GNS3 API
            adapter: Adapter number
            port: Port number
            node_name: Node name (for error messages)

        Returns:
            Error message if port doesn't exist, None if valid
        """
        # If node doesn't have ports info, we can't validate
        # (Some node types like Cloud, NAT don't expose port details)
        if 'ports' not in node:
            logger.debug(f"Node {node_name} has no port information, skipping validation")
            return None

        ports = node['ports']
        if not ports:
            return None

        # Check if requested adapter/port exists
        matching_port = None
        for p in ports:
            p_adapter = p.get('adapter_number', 0)
            p_port = p.get('port_number')

            if p_adapter == adapter and p_port == port:
                matching_port = p
                break

        if not matching_port:
            # Build helpful error with available adapters
            available_adapters = sorted(set(p.get('adapter_number', 0) for p in ports))
            adapter_info = []

            for a in available_adapters:
                adapter_ports = sorted([p.get('port_number', 0)
                                       for p in ports
                                       if p.get('adapter_number', 0) == a])
                adapter_info.append(f"adapter {a}: ports {adapter_ports}")

            return (
                f"Node {node_name} has no port at adapter {adapter} port {port}. "
                f"Available: {', '.join(adapter_info)}"
            )

        return None

    def get_port_info(self, node_name: str) -> Optional[str]:
        """Get human-readable port information for a node

        Args:
            node_name: Node name

        Returns:
            Formatted port information or None if node not found
        """
        if node_name not in self.nodes:
            return None

        node = self.nodes[node_name]

        if 'ports' not in node or not node['ports']:
            return f"Node {node_name} has no port information available"

        ports = node['ports']
        port_by_adapter = {}

        for p in ports:
            adapter = p.get('adapter_number', 0)
            port_num = p.get('port_number', 0)
            port_name = p.get('name', f'port{port_num}')

            if adapter not in port_by_adapter:
                port_by_adapter[adapter] = []

            # Check if port is in use
            in_use = self._is_port_used(node['node_id'], adapter, port_num)
            status = "in use" if in_use else "free"

            port_by_adapter[adapter].append(f"  {port_num}: {port_name} ({status})")

        lines = [f"Ports on {node_name}:"]
        for adapter in sorted(port_by_adapter.keys()):
            lines.append(f"Adapter {adapter}:")
            lines.extend(port_by_adapter[adapter])

        return "\n".join(lines)

    def _is_port_used(self, node_id: str, adapter: int, port: int) -> bool:
        """Check if a port is currently in use

        Args:
            node_id: Node ID
            adapter: Adapter number
            port: Port number

        Returns:
            True if port is in use, False otherwise
        """
        return (node_id in self.port_usage and
                adapter in self.port_usage[node_id] and
                port in self.port_usage[node_id][adapter])
