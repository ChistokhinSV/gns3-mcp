"""
Widget Manager for Traffic Graph Widgets (v0.4.0)

Manages lifecycle of traffic monitoring widgets embedded in GNS3 topology.
Widgets display real-time traffic statistics as mini bar charts via GNS3 Drawing API.

Features:
- Bridge discovery: Maps GNS3 link IDs to ubridge TCP hypervisor bridges
- Traffic monitoring: Queries ubridge via TCP for IN/OUT packet/byte counters
- SVG generation: Creates mini bar charts with RX/TX rates
- State persistence: Saves widget state to JSON file
- Graceful lifecycle: Cleans up widgets on shutdown

v0.4.1: Fixed bridge discovery to use ubridge TCP hypervisor instead of Linux bridges.
GNS3 uses ubridge for networking, not Linux bridges. Each node has its own ubridge
instance running on a unique TCP port. Bridge names follow pattern:
- QEMU-<node_id>-<adapter_number> for QEMU nodes
- <node_id>-<adapter_number> for NAT/cloud nodes
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any

import httpx

from .models import (
    BridgeInfo,
    TopologyInfo,
    TrafficDelta,
    TrafficStats,
    WidgetInfo,
)

logger = logging.getLogger(__name__)

# Constants
WIDGET_WIDTH = 100
WIDGET_HEIGHT = 60
UPDATE_INTERVAL = 15  # seconds
STATE_FILE = "/opt/gns3-ssh-proxy/widgets.json"
UBRIDGE_DISCOVERY_CACHE_TTL = 60  # seconds - how often to refresh ubridge port discovery


class WidgetManager:
    """Manages traffic graph widgets for GNS3 topology"""

    def __init__(
        self,
        gns3_host: str,
        gns3_port: int,
        gns3_username: str,
        gns3_password: str,
        proxy_id: str = "main",
    ):
        self.gns3_host = gns3_host
        self.gns3_port = gns3_port
        self.gns3_username = gns3_username
        self.gns3_password = gns3_password
        self.proxy_id = proxy_id

        # State
        self.widgets: dict[str, WidgetInfo] = {}
        self.jwt_token: str | None = None
        self._update_task: asyncio.Task | None = None
        self._running = False
        self._http_client: httpx.AsyncClient | None = None

        # ubridge discovery cache
        self._ubridge_cache: dict[int, list[str]] = {}  # port -> list of bridge names
        self._ubridge_cache_time: datetime | None = None

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def initialize(self) -> None:
        """Initialize widget manager: load state, recover orphans, start update loop"""
        logger.info("Initializing widget manager...")

        # Create HTTP client
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Authenticate with GNS3
        await self._authenticate()

        # Load saved state
        self._load_state()

        # Verify existing widgets (remove stale, recover orphans)
        await self._verify_widgets()

        # Start update loop
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info(f"Widget manager initialized with {len(self.widgets)} widgets")

    async def shutdown(self) -> None:
        """Shutdown widget manager: stop updates, delete widgets, save state"""
        logger.info("Shutting down widget manager...")
        self._running = False

        # Cancel update task
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Delete all widgets from GNS3
        for widget_id in list(self.widgets.keys()):
            try:
                await self._delete_drawing(
                    self.widgets[widget_id].project_id,
                    self.widgets[widget_id].drawing_id
                )
                logger.info(f"Deleted widget {widget_id}")
            except Exception as e:
                logger.warning(f"Failed to delete widget {widget_id}: {e}")

        # Clear state
        self.widgets.clear()
        self._save_state()

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()

        logger.info("Widget manager shutdown complete")

    # =========================================================================
    # Widget CRUD Operations
    # =========================================================================

    async def create_widget(
        self,
        link_id: str,
        project_id: str,
        x: int | None = None,
        y: int | None = None,
    ) -> WidgetInfo:
        """Create a traffic widget for a link"""
        # Check if widget already exists for this link
        for widget in self.widgets.values():
            if widget.link_id == link_id:
                raise ValueError(f"Widget already exists for link {link_id}")

        # Discover bridge for this link (async, queries ubridge)
        bridge_info = await self._discover_bridge(link_id, project_id)
        if not bridge_info:
            raise ValueError(f"Could not find bridge for link {link_id}")
        ubridge_port, bridge_name = bridge_info

        # Calculate position if not provided (link midpoint)
        if x is None or y is None:
            link_pos = await self._get_link_midpoint(project_id, link_id)
            x = link_pos.get("x", 0) if x is None else x
            y = link_pos.get("y", 0) if y is None else y

        # Read initial stats via ubridge TCP
        stats = await self._ubridge_get_stats(ubridge_port, bridge_name)

        # Generate initial SVG
        svg = self._generate_svg(stats, None)

        # Create drawing in GNS3
        drawing_data = {
            "x": x,
            "y": y,
            "z": 100,  # Above links, below nodes
            "svg": svg,
            "rotation": 0,
            "locked": False,
        }
        drawing = await self._create_drawing(project_id, drawing_data)

        # Create widget info with ubridge connection details
        widget = WidgetInfo(
            widget_id=str(uuid.uuid4()),
            link_id=link_id,
            drawing_id=drawing["drawing_id"],
            bridge_name=bridge_name,
            ubridge_port=ubridge_port,
            proxy_id=self.proxy_id,
            project_id=project_id,
            x=x,
            y=y,
            last_stats=stats,
        )

        # Save to state
        self.widgets[widget.widget_id] = widget
        self._save_state()

        logger.info(f"Created widget {widget.widget_id} for link {link_id} (bridge: {bridge_name}, port: {ubridge_port})")
        return widget

    async def delete_widget(self, widget_id: str) -> WidgetInfo:
        """Delete a traffic widget"""
        if widget_id not in self.widgets:
            raise ValueError(f"Widget {widget_id} not found")

        widget = self.widgets[widget_id]

        # Delete drawing from GNS3
        await self._delete_drawing(widget.project_id, widget.drawing_id)

        # Remove from state
        del self.widgets[widget_id]
        self._save_state()

        logger.info(f"Deleted widget {widget_id}")
        return widget

    def list_widgets(self) -> list[WidgetInfo]:
        """List all widgets"""
        return list(self.widgets.values())

    async def refresh_widgets(self) -> int:
        """Force immediate refresh of all widgets"""
        count = await self._update_all_widgets()
        return count

    # =========================================================================
    # ubridge Discovery and TCP Client
    # =========================================================================

    async def _discover_ubridge_ports(self) -> list[int]:
        """Discover ubridge TCP ports by scanning /proc on GNS3 host.

        Container runs with pid: host, so we can see host processes via /proc.
        This is more reliable than 'ps aux' which doesn't work well in slim containers.
        """
        ports = []
        proc_path = "/proc"
        try:
            for entry in os.listdir(proc_path):
                if not entry.isdigit():
                    continue
                cmdline_path = os.path.join(proc_path, entry, "cmdline")
                try:
                    with open(cmdline_path, "r") as f:
                        cmdline = f.read()
                    if "ubridge" in cmdline and "-H" in cmdline:
                        # cmdline uses null separators, convert to space
                        cmdline = cmdline.replace("\x00", " ")
                        # Extract port from "-H 0.0.0.0:PORT" or "-H :PORT"
                        match = re.search(r"-H\s+[\d.]*:?(\d+)", cmdline)
                        if match:
                            ports.append(int(match.group(1)))
                except (OSError, IOError):
                    # Process may have exited or we don't have permission
                    continue
            logger.debug(f"Discovered ubridge ports: {ports}")
            return ports
        except Exception as e:
            logger.warning(f"Error discovering ubridge ports: {e}")
            return []

    async def _ubridge_list_bridges(self, port: int) -> list[str]:
        """Get bridge list from ubridge via TCP."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=5.0
            )
            try:
                writer.write(b"bridge list\n")
                await writer.drain()
                response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
                bridges = []
                for line in response.decode().split("\n"):
                    # Parse: "101 QEMU-xxx-0 (NIOs = 2)"
                    match = re.match(r"101\s+(\S+)", line)
                    if match:
                        bridges.append(match.group(1))
                return bridges
            finally:
                writer.close()
                await writer.wait_closed()
        except asyncio.TimeoutError:
            logger.debug(f"Timeout connecting to ubridge port {port}")
            return []
        except ConnectionRefusedError:
            logger.debug(f"Connection refused to ubridge port {port}")
            return []
        except Exception as e:
            logger.debug(f"Error querying ubridge port {port}: {e}")
            return []

    async def _ubridge_get_stats(self, port: int, bridge_name: str) -> TrafficStats:
        """Get traffic stats from ubridge via TCP."""
        stats = TrafficStats(timestamp=datetime.utcnow())
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=5.0
            )
            try:
                writer.write(f"bridge get_stats {bridge_name}\n".encode())
                await writer.drain()
                response = await asyncio.wait_for(reader.read(4096), timeout=5.0)

                for line in response.decode().split("\n"):
                    # Parse: "101 Source NIO: IN: 272 packets (41927 bytes) OUT: 2704 packets (235833 bytes)"
                    match = re.match(
                        r"101\s+(Source|Destination) NIO:\s+"
                        r"IN:\s+(\d+) packets \((\d+) bytes\)\s+"
                        r"OUT:\s+(\d+) packets \((\d+) bytes\)",
                        line
                    )
                    if match:
                        nio_type = match.group(1)
                        in_pkts = int(match.group(2))
                        in_bytes = int(match.group(3))
                        out_pkts = int(match.group(4))
                        out_bytes = int(match.group(5))

                        if nio_type == "Source":
                            # Source NIO represents the node's perspective:
                            # - IN = traffic received by this node
                            # - OUT = traffic sent by this node
                            stats.rx_packets = in_pkts
                            stats.rx_bytes = in_bytes
                            stats.tx_packets = out_pkts
                            stats.tx_bytes = out_bytes
                        # Ignore Destination NIO - it's the same traffic from other end

                return stats
            finally:
                writer.close()
                await writer.wait_closed()
        except Exception as e:
            logger.warning(f"Error getting stats from ubridge port {port}: {e}")
            return stats

    async def _refresh_ubridge_cache(self) -> None:
        """Refresh the ubridge port -> bridges cache."""
        now = datetime.utcnow()
        if (
            self._ubridge_cache_time is not None
            and (now - self._ubridge_cache_time).total_seconds() < UBRIDGE_DISCOVERY_CACHE_TTL
        ):
            return  # Cache is still valid

        logger.debug("Refreshing ubridge cache...")
        self._ubridge_cache = {}
        ports = await self._discover_ubridge_ports()
        for port in ports:
            bridges = await self._ubridge_list_bridges(port)
            if bridges:
                self._ubridge_cache[port] = bridges
        self._ubridge_cache_time = now
        logger.debug(f"ubridge cache refreshed: {len(self._ubridge_cache)} ports")

    async def _discover_bridge(
        self, link_id: str, project_id: str
    ) -> tuple[int, str] | None:
        """
        Discover ubridge port and bridge name for a GNS3 link.

        Returns (ubridge_port, bridge_name) or None if not found.

        GNS3 bridge naming:
        - QEMU-<node_id>-<adapter_number> for QEMU nodes
        - <node_id>-<adapter_number> for NAT/cloud nodes
        """
        # 1. Get link info from GNS3 API
        try:
            link = await self._get_link(project_id, link_id)
        except Exception as e:
            logger.warning(f"Failed to get link {link_id}: {e}")
            return None

        nodes = link.get("nodes", [])
        if len(nodes) < 2:
            logger.warning(f"Link {link_id} has fewer than 2 nodes")
            return None

        # 2. Construct expected bridge names for both endpoints
        # We try node_a first, then node_b if needed
        bridge_candidates = []
        for node_ref in nodes[:2]:
            node_id = node_ref.get("node_id")
            adapter = node_ref.get("adapter_number", 0)
            bridge_candidates.extend([
                f"QEMU-{node_id}-{adapter}",
                f"{node_id}-{adapter}",
            ])

        # 3. Refresh ubridge cache if needed
        await self._refresh_ubridge_cache()

        # 4. Search for matching bridge - iterate candidates first to respect
        # link node ordering (first node in link is preferred)
        for candidate in bridge_candidates:
            for port, bridges in self._ubridge_cache.items():
                for bridge_name in bridges:
                    if candidate in bridge_name or bridge_name == candidate:
                        logger.debug(
                            f"Found bridge {bridge_name} on port {port} for link {link_id}"
                        )
                        return (port, bridge_name)

        logger.warning(f"Could not find bridge for link {link_id}")
        return None

    async def list_bridges(self) -> list[BridgeInfo]:
        """List all available ubridge bridges with their stats."""
        bridges = []

        # Refresh cache
        await self._refresh_ubridge_cache()

        for port, bridge_names in self._ubridge_cache.items():
            for bridge_name in bridge_names:
                # Get stats for this bridge
                stats = await self._ubridge_get_stats(port, bridge_name)

                # Try to extract node_id and adapter from bridge name
                node_id = None
                adapter = None
                # Pattern: "QEMU-<uuid>-<adapter>" or "<uuid>-<adapter>"
                match = re.match(r"(?:QEMU-)?([a-f0-9-]+)-(\d+)$", bridge_name)
                if match:
                    node_id = match.group(1)
                    adapter = int(match.group(2))

                # Check if widget exists for this bridge
                has_widget = any(
                    w.bridge_name == bridge_name for w in self.widgets.values()
                )

                bridges.append(BridgeInfo(
                    name=bridge_name,
                    ubridge_port=port,
                    node_id=node_id,
                    adapter=adapter,
                    stats=stats,
                    has_widget=has_widget,
                ))

        return bridges

    async def _get_link(
        self,
        project_id: str,
        link_id: str,
    ) -> dict[str, Any]:
        """Get link details from GNS3 API."""
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/links/{link_id}"
        assert self._http_client is not None
        response = await self._http_client.get(
            url,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Traffic Statistics
    # =========================================================================

    def _calculate_delta(
        self,
        current: TrafficStats,
        previous: TrafficStats | None,
    ) -> TrafficDelta:
        """Calculate traffic rate from two measurements"""
        if previous is None:
            return TrafficDelta()

        interval = (current.timestamp - previous.timestamp).total_seconds()
        if interval <= 0:
            return TrafficDelta()

        return TrafficDelta(
            rx_bps=(current.rx_bytes - previous.rx_bytes) / interval,
            tx_bps=(current.tx_bytes - previous.tx_bytes) / interval,
            rx_pps=(current.rx_packets - previous.rx_packets) / interval,
            tx_pps=(current.tx_packets - previous.tx_packets) / interval,
            interval_seconds=interval,
        )

    # =========================================================================
    # SVG Generation
    # =========================================================================

    def _format_rate(self, bps: float) -> str:
        """Format bytes/sec as human readable string"""
        if bps >= 1_000_000_000:
            return f"{bps / 1_000_000_000:.1f}G"
        elif bps >= 1_000_000:
            return f"{bps / 1_000_000:.1f}M"
        elif bps >= 1_000:
            return f"{bps / 1_000:.1f}K"
        else:
            return f"{bps:.0f}"

    def _generate_svg(
        self,
        stats: TrafficStats,
        delta: TrafficDelta | None,
    ) -> str:
        """Generate mini bar chart SVG widget"""
        rx_rate = delta.rx_bps if delta else 0
        tx_rate = delta.tx_bps if delta else 0

        # Calculate bar heights (max 40px)
        max_rate = max(rx_rate, tx_rate, 1)  # Avoid division by zero
        rx_height = int((rx_rate / max_rate) * 40) if max_rate > 0 else 2
        tx_height = int((tx_rate / max_rate) * 40) if max_rate > 0 else 2

        # Minimum height for visibility
        rx_height = max(rx_height, 2)
        tx_height = max(tx_height, 2)

        # Bar Y positions (bars grow upward from y=50)
        rx_y = 50 - rx_height
        tx_y = 50 - tx_height

        # Format rate labels
        rx_label = self._format_rate(rx_rate)
        tx_label = self._format_rate(tx_rate)

        svg = f'''<svg width="{WIDGET_WIDTH}" height="{WIDGET_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect x="0" y="0" width="{WIDGET_WIDTH}" height="{WIDGET_HEIGHT}"
        fill="#1a1a2e" stroke="#4a4a6a" stroke-width="1" rx="3"/>

  <!-- RX Bar (green) -->
  <rect x="15" y="{rx_y}" width="30" height="{rx_height}"
        fill="#00ff88" opacity="0.8"/>

  <!-- TX Bar (blue) -->
  <rect x="55" y="{tx_y}" width="30" height="{tx_height}"
        fill="#00aaff" opacity="0.8"/>

  <!-- Labels -->
  <text x="30" y="57" font-family="monospace" font-size="7"
        fill="#888" text-anchor="middle">RX</text>
  <text x="70" y="57" font-family="monospace" font-size="7"
        fill="#888" text-anchor="middle">TX</text>

  <!-- Rate values -->
  <text x="30" y="8" font-family="monospace" font-size="7"
        fill="#00ff88" text-anchor="middle">{rx_label}</text>
  <text x="70" y="8" font-family="monospace" font-size="7"
        fill="#00aaff" text-anchor="middle">{tx_label}</text>

  <!-- Widget metadata (hidden) -->
  <desc>gns3-traffic-widget:proxy={self.proxy_id}</desc>
</svg>'''
        return svg

    # =========================================================================
    # Update Loop
    # =========================================================================

    async def _update_loop(self) -> None:
        """Background task to update all widgets every UPDATE_INTERVAL seconds"""
        while self._running:
            try:
                await asyncio.sleep(UPDATE_INTERVAL)
                if self._running:
                    await self._update_all_widgets()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}")

    async def _update_all_widgets(self) -> int:
        """Update SVG for all widgets with current traffic data"""
        updated = 0
        for widget in list(self.widgets.values()):
            try:
                # Read current stats via ubridge TCP
                stats = await self._ubridge_get_stats(
                    widget.ubridge_port, widget.bridge_name
                )

                # Calculate delta from previous stats
                delta = self._calculate_delta(stats, widget.last_stats)

                # Generate new SVG
                svg = self._generate_svg(stats, delta)

                # Update drawing in GNS3
                await self._update_drawing(
                    widget.project_id,
                    widget.drawing_id,
                    {"svg": svg}
                )

                # Update widget state
                widget.last_stats = stats
                widget.last_delta = delta
                widget.last_update = datetime.utcnow()
                updated += 1

            except Exception as e:
                logger.warning(f"Failed to update widget {widget.widget_id}: {e}")

        if updated > 0:
            self._save_state()
            logger.debug(f"Updated {updated} widgets")

        return updated

    # =========================================================================
    # State Persistence
    # =========================================================================

    def _load_state(self) -> None:
        """Load widget state from JSON file"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)

                if data.get("version") != "1.0":
                    logger.warning(f"Unknown state file version: {data.get('version')}")
                    return

                for widget_data in data.get("widgets", {}).values():
                    # Only load widgets owned by this proxy
                    if widget_data.get("proxy_id") == self.proxy_id:
                        widget = WidgetInfo(**widget_data)
                        self.widgets[widget.widget_id] = widget

                logger.info(f"Loaded {len(self.widgets)} widgets from state file")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")

    def _save_state(self) -> None:
        """Save widget state to JSON file"""
        try:
            # Read existing state (may have widgets from other proxies)
            existing_data: dict[str, Any] = {"version": "1.0", "widgets": {}}
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r") as f:
                    existing_data = json.load(f)

            # Update with our widgets
            widgets_dict = existing_data.get("widgets", {})

            # Remove our old widgets
            widgets_dict = {
                k: v for k, v in widgets_dict.items()
                if v.get("proxy_id") != self.proxy_id
            }

            # Add current widgets
            for widget_id, widget in self.widgets.items():
                widgets_dict[widget_id] = widget.model_dump(mode="json")

            # Write back
            data = {
                "version": "1.0",
                "widgets": widgets_dict,
            }

            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)

        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    async def _verify_widgets(self) -> None:
        """Verify widgets exist in GNS3, remove stale entries"""
        to_remove = []
        for widget_id, widget in self.widgets.items():
            try:
                # Check if drawing still exists
                await self._get_drawing(widget.project_id, widget.drawing_id)
            except Exception:
                logger.warning(f"Widget {widget_id} drawing not found, removing")
                to_remove.append(widget_id)

        for widget_id in to_remove:
            del self.widgets[widget_id]

        if to_remove:
            self._save_state()

    # =========================================================================
    # GNS3 API Integration
    # =========================================================================

    async def _authenticate(self) -> None:
        """Authenticate with GNS3 and get JWT token"""
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/access/users/authenticate"
        try:
            assert self._http_client is not None
            response = await self._http_client.post(
                url,
                json={
                    "username": self.gns3_username,
                    "password": self.gns3_password,
                },
            )
            response.raise_for_status()
            self.jwt_token = response.json().get("access_token")
            logger.info("Authenticated with GNS3 server")
        except Exception as e:
            logger.error(f"Failed to authenticate with GNS3: {e}")
            raise

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers with JWT token"""
        return {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json",
        }

    async def _create_drawing(
        self,
        project_id: str,
        drawing_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a drawing in GNS3"""
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/drawings"
        assert self._http_client is not None
        response = await self._http_client.post(
            url,
            headers=self._get_headers(),
            json=drawing_data,
        )
        response.raise_for_status()
        return response.json()

    async def _update_drawing(
        self,
        project_id: str,
        drawing_id: str,
        drawing_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a drawing in GNS3"""
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/drawings/{drawing_id}"
        assert self._http_client is not None
        response = await self._http_client.put(
            url,
            headers=self._get_headers(),
            json=drawing_data,
        )
        response.raise_for_status()
        return response.json()

    async def _delete_drawing(self, project_id: str, drawing_id: str) -> None:
        """Delete a drawing from GNS3"""
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/drawings/{drawing_id}"
        assert self._http_client is not None
        response = await self._http_client.delete(
            url,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    async def _get_drawing(
        self,
        project_id: str,
        drawing_id: str,
    ) -> dict[str, Any]:
        """Get a drawing from GNS3"""
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/drawings/{drawing_id}"
        assert self._http_client is not None
        response = await self._http_client.get(
            url,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    async def _get_link_midpoint(
        self,
        project_id: str,
        link_id: str,
    ) -> dict[str, int]:
        """Get the midpoint position of a link for widget placement"""
        # Get link details
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/links/{link_id}"
        assert self._http_client is not None
        response = await self._http_client.get(
            url,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        link = response.json()

        # Get node positions for both endpoints
        nodes = link.get("nodes", [])
        if len(nodes) < 2:
            return {"x": 0, "y": 0}

        positions = []
        for node_ref in nodes[:2]:
            node_id = node_ref.get("node_id")
            node_url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/nodes/{node_id}"
            node_response = await self._http_client.get(
                node_url,
                headers=self._get_headers(),
            )
            node_response.raise_for_status()
            node = node_response.json()
            positions.append((node.get("x", 0), node.get("y", 0)))

        # Calculate midpoint
        mid_x = int((positions[0][0] + positions[1][0]) / 2)
        mid_y = int((positions[0][1] + positions[1][1]) / 2)

        return {"x": mid_x, "y": mid_y}

    async def get_topology(self, project_id: str) -> TopologyInfo:
        """Get project topology for web UI"""
        assert self._http_client is not None

        # Get project info
        project_url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}"
        project_response = await self._http_client.get(
            project_url,
            headers=self._get_headers(),
        )
        project_response.raise_for_status()
        project = project_response.json()

        # Get nodes
        nodes_url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/nodes"
        nodes_response = await self._http_client.get(
            nodes_url,
            headers=self._get_headers(),
        )
        nodes_response.raise_for_status()
        nodes = nodes_response.json()

        # Get links
        links_url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/links"
        links_response = await self._http_client.get(
            links_url,
            headers=self._get_headers(),
        )
        links_response.raise_for_status()
        links = links_response.json()

        # Get widgets for this project
        widgets = [w for w in self.widgets.values() if w.project_id == project_id]

        return TopologyInfo(
            project_id=project_id,
            project_name=project.get("name", "Unknown"),
            nodes=nodes,
            links=links,
            widgets=widgets,
        )

    async def get_projects(self) -> list[dict[str, Any]]:
        """Get list of GNS3 projects"""
        assert self._http_client is not None
        url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects"
        response = await self._http_client.get(
            url,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()
