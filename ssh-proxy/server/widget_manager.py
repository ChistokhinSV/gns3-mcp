"""
Widget Manager for Traffic Graph Widgets (v0.5.0)

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

v0.4.2: Widget visualization enhancements:
- inverse flag: Swap TX/RX direction to show traffic from second node's perspective
- chart_type: Support for "bar" (default) and "timeseries" charts
- Direction arrow: Visual indicator showing traffic flow direction
- History buffer: Circular buffer (30 data points) for time-series charts
- Time-series SVG: Area chart with TX above line (blue), RX below (green)

v0.4.3: Widget update support & improved visibility:
- update_widget(): Modify inverse, chart_type, position without recreation
- Arrows now larger (15x12px) and bright orange (#ff8800) for visibility
- Arrow has stroke outline for better contrast

v0.5.0: Dynamic icon sizes for accurate topology rendering:
- Node centers calculated based on icon type (PNG=78px, SVG=58px)
- Widget midpoints use icon-aware center calculation
- Frontend receives icon_size per node for correct link positioning
"""

import asyncio
import json
import logging
import math
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


def _get_icon_size(symbol: str | None) -> int:
    """Determine icon size based on symbol type.

    GNS3 uses different icon sizes:
    - PNG symbols (custom icons): 78×78 pixels
    - SVG symbols (builtin icons): 58×58 pixels
    """
    if symbol and symbol.lower().endswith(".png"):
        return 78
    return 58


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
        inverse: bool = False,
        chart_type: str = "bar",
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

        # Calculate position and angle (always need angle for arrow direction)
        link_pos = await self._get_link_midpoint(project_id, link_id)
        angle = link_pos.get("angle", 0.0)
        # Offset by half widget size to center it (GNS3 uses top-left corner)
        if x is None:
            x = link_pos.get("x", 0) - WIDGET_WIDTH // 2
        if y is None:
            y = link_pos.get("y", 0) - WIDGET_HEIGHT // 2

        # Read initial stats via ubridge TCP
        stats = await self._ubridge_get_stats(ubridge_port, bridge_name)

        # Apply inverse flag (swap TX/RX if requested)
        if inverse:
            stats = self._swap_stats(stats)

        # Generate initial SVG (based on chart_type, with rotated arrow)
        svg = self._generate_svg(stats, None, inverse=inverse, chart_type=chart_type, angle=angle)

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
            angle=angle,  # Direction angle for arrow rotation
            inverse=inverse,
            chart_type=chart_type,
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

    async def update_widget(
        self,
        widget_id: str,
        inverse: bool | None = None,
        chart_type: str | None = None,
        x: int | None = None,
        y: int | None = None,
    ) -> WidgetInfo:
        """Update widget parameters (inverse, chart_type, position)

        Changes take effect on next update cycle (15 seconds).
        Position changes are applied immediately.
        """
        if widget_id not in self.widgets:
            raise ValueError(f"Widget {widget_id} not found")

        widget = self.widgets[widget_id]
        changed = False

        # Update parameters if provided
        if inverse is not None and inverse != widget.inverse:
            widget.inverse = inverse
            # Clear history when changing direction (data would be confusing)
            widget.history = []
            changed = True

        if chart_type is not None and chart_type != widget.chart_type:
            if chart_type not in ("bar", "timeseries"):
                raise ValueError(f"Invalid chart_type: {chart_type}. Must be 'bar' or 'timeseries'")
            widget.chart_type = chart_type
            changed = True

        # Update position if provided
        position_changed = False
        if x is not None and x != widget.x:
            widget.x = x
            position_changed = True
        if y is not None and y != widget.y:
            widget.y = y
            position_changed = True

        # Apply position change to GNS3 drawing immediately
        if position_changed:
            await self._update_drawing(
                widget.project_id,
                widget.drawing_id,
                {"x": widget.x, "y": widget.y}
            )
            changed = True

        # Regenerate SVG if chart settings changed (applies new arrow direction)
        if inverse is not None or chart_type is not None:
            svg = self._generate_svg(
                widget.last_stats,
                widget.last_delta,
                inverse=widget.inverse,
                chart_type=widget.chart_type,
                history=widget.history,
                angle=widget.angle,
            )
            await self._update_drawing(
                widget.project_id,
                widget.drawing_id,
                {"svg": svg}
            )

        if changed:
            self._save_state()
            logger.info(f"Updated widget {widget_id}")

        return widget

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

    def _swap_stats(self, stats: TrafficStats) -> TrafficStats:
        """Swap TX/RX values for inverse mode (second node's perspective)"""
        return TrafficStats(
            rx_bytes=stats.tx_bytes,
            tx_bytes=stats.rx_bytes,
            rx_packets=stats.tx_packets,
            tx_packets=stats.rx_packets,
            rx_errors=stats.tx_errors,
            tx_errors=stats.rx_errors,
            timestamp=stats.timestamp,
        )

    def _swap_delta(self, delta: TrafficDelta) -> TrafficDelta:
        """Swap TX/RX values in delta for inverse mode"""
        return TrafficDelta(
            rx_bps=delta.tx_bps,
            tx_bps=delta.rx_bps,
            rx_pps=delta.tx_pps,
            tx_pps=delta.rx_pps,
            interval_seconds=delta.interval_seconds,
        )

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
        inverse: bool = False,
        chart_type: str = "bar",
        history: list[TrafficDelta] | None = None,
        angle: float = 0.0,
    ) -> str:
        """Generate SVG widget based on chart_type"""
        if chart_type == "timeseries" and history:
            return self._generate_timeseries_svg(history, inverse, angle)
        else:
            return self._generate_bar_svg(delta, inverse, angle)

    def _generate_bar_svg(
        self,
        delta: TrafficDelta | None,
        inverse: bool = False,
        angle: float = 0.0,
    ) -> str:
        """Generate mini bar chart SVG widget with direction arrow"""
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

        # Direction arrow: rotated based on actual node positions
        # If inverse, reverse direction (+180°)
        arrow_angle = angle + 180 if inverse else angle
        # Arrow at top center (50, 6) to avoid overlapping bars
        # Smaller arrow: 6px long, 8px tall - fits between rate labels
        # Base edge has bright orange-red to indicate direction
        arrow = f'''<g transform="rotate({arrow_angle:.1f}, 50, 6)">
    <polygon points="56,6 50,2 50,10" fill="#ff8800" stroke="#cc6600" stroke-width="1"/>
    <line x1="50" y1="2" x2="50" y2="10" stroke="#ff4400" stroke-width="2"/>
  </g>'''

        svg = f'''<svg width="{WIDGET_WIDTH}" height="{WIDGET_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect x="0" y="0" width="{WIDGET_WIDTH}" height="{WIDGET_HEIGHT}"
        fill="#1a1a2e" stroke="#4a4a6a" stroke-width="1" rx="3"/>

  <!-- Direction Arrow -->
  {arrow}

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

    def _generate_timeseries_svg(
        self,
        history: list[TrafficDelta],
        inverse: bool = False,
        angle: float = 0.0,
    ) -> str:
        """Generate time-series area chart SVG widget.

        Layout: TX (blue) above center line, RX (green) below.
        Time flows left-to-right (oldest on left, newest on right).
        """
        width, height = WIDGET_WIDTH, WIDGET_HEIGHT  # Same as bar widget (100x60)
        mid_y = height // 2  # Zero line at center (30)
        margin_x = 5
        margin_y = 5
        graph_width = width - 2 * margin_x  # 90
        graph_height = mid_y - margin_y  # 25 pixels for each direction

        # Need at least 2 points for a graph
        if len(history) < 2:
            # Return empty placeholder
            return f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#1a1a2e" stroke="#4a4a6a" stroke-width="1" rx="3"/>
  <line x1="{margin_x}" y1="{mid_y}" x2="{width-margin_x}" y2="{mid_y}" stroke="#444" stroke-width="1"/>
  <text x="{width//2}" y="{mid_y + 3}" font-family="monospace" font-size="8" fill="#666" text-anchor="middle">...</text>
  <desc>gns3-traffic-widget:proxy={self.proxy_id}</desc>
</svg>'''

        # Find max rate for scaling (use same scale for TX and RX for comparison)
        max_rate = max(
            max((d.tx_bps for d in history), default=1),
            max((d.rx_bps for d in history), default=1),
            1  # Minimum to avoid division by zero
        )

        # Build paths for TX (above) and RX (below)
        num_points = len(history)
        x_step = graph_width / (num_points - 1) if num_points > 1 else graph_width

        # TX path (above zero line - grows upward)
        tx_points = []
        for i, delta in enumerate(history):
            x = margin_x + i * x_step
            # Scale to graph_height, subtract from mid_y to grow upward
            y = mid_y - (delta.tx_bps / max_rate) * graph_height
            tx_points.append(f"{x:.1f},{y:.1f}")

        # Close TX path as area (down to zero line, back to start)
        tx_path = (
            f"M {margin_x},{mid_y} "
            f"L {' L '.join(tx_points)} "
            f"L {margin_x + (num_points - 1) * x_step},{mid_y} Z"
        )

        # RX path (below zero line - grows downward)
        rx_points = []
        for i, delta in enumerate(history):
            x = margin_x + i * x_step
            # Scale to graph_height, add to mid_y to grow downward
            y = mid_y + (delta.rx_bps / max_rate) * graph_height
            rx_points.append(f"{x:.1f},{y:.1f}")

        # Close RX path as area (up to zero line, back to start)
        rx_path = (
            f"M {margin_x},{mid_y} "
            f"L {' L '.join(rx_points)} "
            f"L {margin_x + (num_points - 1) * x_step},{mid_y} Z"
        )

        # Current values (latest point)
        latest = history[-1]
        tx_label = self._format_rate(latest.tx_bps)
        rx_label = self._format_rate(latest.rx_bps)

        # Direction arrow: rotated based on actual node positions
        # If inverse, reverse direction (+180°)
        arrow_angle = angle + 180 if inverse else angle
        # Arrow centered at widget center (50, 30), pointing right at 0°
        # Base edge has bright orange-red to indicate direction
        arrow = f'''<g transform="rotate({arrow_angle:.1f}, 50, 30)">
    <polygon points="60,30 50,24 50,36" fill="#ff8800" stroke="#cc6600" stroke-width="1"/>
    <line x1="50" y1="24" x2="50" y2="36" stroke="#ff4400" stroke-width="2"/>
  </g>'''

        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="100%" height="100%" fill="#1a1a2e" stroke="#4a4a6a" stroke-width="1" rx="3"/>

  <!-- Zero line -->
  <line x1="{margin_x}" y1="{mid_y}" x2="{width - margin_x}" y2="{mid_y}" stroke="#444" stroke-width="1"/>

  <!-- TX area (blue, above line) -->
  <path d="{tx_path}" fill="#00aaff" opacity="0.6"/>

  <!-- RX area (green, below line) -->
  <path d="{rx_path}" fill="#00ff88" opacity="0.6"/>

  <!-- Current value labels -->
  <text x="{width - 3}" y="10" font-family="monospace" font-size="7" fill="#00aaff" text-anchor="end">{tx_label}</text>
  <text x="{width - 3}" y="{height - 3}" font-family="monospace" font-size="7" fill="#00ff88" text-anchor="end">{rx_label}</text>

  <!-- Direction arrow -->
  {arrow}

  <!-- Widget metadata (hidden) -->
  <desc>gns3-traffic-widget:proxy={self.proxy_id}:timeseries</desc>
</svg>'''
        return svg

    # =========================================================================
    # Update Loop
    # =========================================================================

    async def _update_loop(self) -> None:
        """Background task to update all widgets every UPDATE_INTERVAL seconds"""
        verify_counter = 0
        while self._running:
            try:
                await asyncio.sleep(UPDATE_INTERVAL)
                if self._running:
                    await self._update_all_widgets()
                    # Verify widgets every 6 cycles (~30s) to clean up orphans
                    verify_counter += 1
                    if verify_counter >= 6:
                        verify_counter = 0
                        await self._verify_widgets()
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

                # Apply inverse flag (swap TX/RX if requested)
                if widget.inverse:
                    stats = self._swap_stats(stats)

                # Calculate delta from previous stats
                delta = self._calculate_delta(stats, widget.last_stats)

                # Add delta to history (circular buffer for time-series chart)
                if delta:
                    widget.history.append(delta)
                    # Trim to max_history
                    if len(widget.history) > widget.max_history:
                        widget.history = widget.history[-widget.max_history:]

                # Generate new SVG (based on chart_type)
                svg = self._generate_svg(
                    stats, delta,
                    inverse=widget.inverse,
                    chart_type=widget.chart_type,
                    history=widget.history,
                    angle=widget.angle,
                )

                # Update drawing in GNS3
                try:
                    await self._update_drawing(
                        widget.project_id,
                        widget.drawing_id,
                        {"svg": svg}
                    )
                except Exception as update_err:
                    # Drawing might have been deleted - try to recreate
                    logger.warning(f"Update failed for widget {widget.widget_id}, recreating: {update_err}")
                    new_drawing_id = await self._recreate_widget_drawing(widget)
                    if new_drawing_id:
                        widget.drawing_id = new_drawing_id
                        logger.info(f"Recreated drawing for widget {widget.widget_id}")
                    else:
                        raise update_err

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
        """Verify widgets: remove orphans (deleted links), recreate missing drawings"""
        recreated = 0
        to_remove = []

        for widget_id, widget in self.widgets.items():
            # First check if the link still exists
            try:
                await self._get_link(widget.project_id, widget.link_id)
            except Exception:
                # Link was deleted - remove the widget
                logger.warning(f"Widget {widget_id} link {widget.link_id} no longer exists, removing widget")
                to_remove.append(widget_id)
                # Also delete the drawing if it exists
                try:
                    await self._delete_drawing(widget.project_id, widget.drawing_id)
                except Exception:
                    pass  # Drawing may already be gone
                continue

            # Link exists - check if drawing still exists
            try:
                await self._get_drawing(widget.project_id, widget.drawing_id)
            except Exception:
                # Drawing not found - try to recreate it
                logger.warning(f"Widget {widget_id} drawing not found, recreating...")
                try:
                    new_drawing_id = await self._recreate_widget_drawing(widget)
                    if new_drawing_id:
                        widget.drawing_id = new_drawing_id
                        recreated += 1
                        logger.info(f"Recreated drawing for widget {widget_id}")
                    else:
                        to_remove.append(widget_id)
                except Exception as e:
                    logger.warning(f"Failed to recreate widget {widget_id}: {e}")
                    to_remove.append(widget_id)

        for widget_id in to_remove:
            if widget_id in self.widgets:
                del self.widgets[widget_id]
                logger.warning(f"Removed stale widget {widget_id}")

        if recreated > 0 or to_remove:
            self._save_state()

    async def _recreate_widget_drawing(self, widget: WidgetInfo) -> str | None:
        """Recreate a missing drawing for a widget. Returns new drawing_id or None."""
        try:
            # Get current stats to generate SVG
            stats = await self._ubridge_get_stats(widget.ubridge_port, widget.bridge_name)

            if widget.inverse:
                stats = self._swap_stats(stats)

            # Generate SVG with current state
            svg = self._generate_svg(
                stats, None,
                inverse=widget.inverse,
                chart_type=widget.chart_type,
                history=widget.history,
                angle=widget.angle,
            )

            # Create new drawing in GNS3
            drawing_data = {
                "x": widget.x,
                "y": widget.y,
                "z": 100,
                "svg": svg,
                "rotation": 0,
                "locked": False,
            }
            drawing = await self._create_drawing(widget.project_id, drawing_data)
            return drawing["drawing_id"]

        except Exception as e:
            logger.warning(f"Failed to recreate drawing: {e}")
            return None

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

        centers = []
        for node_ref in nodes[:2]:
            node_id = node_ref.get("node_id")
            node_url = f"http://{self.gns3_host}:{self.gns3_port}/v3/projects/{project_id}/nodes/{node_id}"
            node_response = await self._http_client.get(
                node_url,
                headers=self._get_headers(),
            )
            node_response.raise_for_status()
            node = node_response.json()
            # Calculate node center based on icon size
            icon_size = _get_icon_size(node.get("symbol"))
            center_x = node.get("x", 0) + icon_size // 2
            center_y = node.get("y", 0) + icon_size // 2
            centers.append((center_x, center_y))

        # Calculate midpoint between node centers
        mid_x = int((centers[0][0] + centers[1][0]) / 2)
        mid_y = int((centers[0][1] + centers[1][1]) / 2)

        # Calculate angle from node1 to node2 (degrees, 0° = right)
        dx = centers[1][0] - centers[0][0]
        dy = centers[1][1] - centers[0][1]
        angle = math.degrees(math.atan2(dy, dx))

        return {"x": mid_x, "y": mid_y, "angle": angle}

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

        # Add icon_size to each node for frontend rendering
        for node in nodes:
            node["icon_size"] = _get_icon_size(node.get("symbol"))

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
