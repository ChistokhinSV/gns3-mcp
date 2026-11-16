"""Is a newer gns3-mcp on PyPI? (GM-110)

gns3_connection(action="check") asks. The answer must not slow the check down, so it
waits at most CHECK_WINDOW (300 ms). A lookup that takes longer keeps running in the
background and fills the cache for the next check; slow networks and errors simply
mean nothing is reported. GNS3_MCP_UPDATE_CHECK=false turns the lookup off.
"""

import asyncio
import logging
import os
import re
import ssl
import time
import warnings

import httpx

logger = logging.getLogger(__name__)

PYPI_JSON = "https://pypi.org/pypi/gns3-mcp/json"
CHECK_WINDOW = 0.3  # seconds a check may wait for the answer
FETCH_TIMEOUT = 5.0  # the lookup itself, which may finish after the window
CACHE_TTL = 6 * 3600  # an answer is reused this long
DISABLE_ENV = "GNS3_MCP_UPDATE_CHECK"
AUTO_UPDATE_ENV = "GNS3_MCP_AUTO_UPDATE"  # written by `gns3-mcp configure`

_cached: tuple[float, str] | None = None
_task: asyncio.Task | None = None
_ssl: ssl.SSLContext | None = None


def _ssl_context() -> ssl.SSLContext:
    """The OS trust store plus certifi, built once.

    The OS store covers networks that inspect TLS; certifi covers Pythons without one.
    Building it takes ~0.2 s, so it is reused (httpx would rebuild it per client).
    """
    global _ssl
    if _ssl is None:
        with warnings.catch_warnings():
            # Windows: "Bad certificate in Windows certificate store" for unrelated entries
            warnings.simplefilter("ignore")
            context = ssl.create_default_context()
            try:
                import certifi

                context.load_verify_locations(certifi.where())
            except Exception:
                pass
        _ssl = context
    return _ssl


def _version_key(version: str) -> tuple[int, ...] | None:
    """(0, 61, 0) for "0.61.0"; None for pre-releases and anything else"""
    if not re.fullmatch(r"\d+(\.\d+)*", version.strip()):
        return None
    parts = [int(p) for p in version.strip().split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer(latest: str, installed: str) -> bool:
    new, old = _version_key(latest), _version_key(installed)
    return new is not None and old is not None and new > old


async def _fetch() -> str | None:
    global _cached
    try:
        context = await asyncio.to_thread(_ssl_context)  # keep the event loop free
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, verify=context) as client:
            response = await client.get(PYPI_JSON, headers={"Accept": "application/json"})
            response.raise_for_status()
            version = str(response.json()["info"]["version"])
    except Exception as e:
        logger.debug(f"Update check failed: {type(e).__name__}: {e}")
        return None
    _cached = (time.monotonic(), version)
    return version


async def latest_version(window: float = CHECK_WINDOW) -> str | None:
    """The newest version on PyPI, or None if it is not known within `window` seconds"""
    global _task
    if os.environ.get(DISABLE_ENV, "").strip().lower() in ("0", "false", "no", "off"):
        return None
    if _cached and time.monotonic() - _cached[0] < CACHE_TTL:
        return _cached[1]
    if _task is None or _task.done():
        _task = asyncio.create_task(_fetch())
    try:
        # shield: on timeout the lookup goes on and fills the cache for the next check
        return await asyncio.wait_for(asyncio.shield(_task), window)
    except (asyncio.TimeoutError, Exception):
        return None


def how_to_update() -> str:
    """The update path for this install; the saved configure choice decides when known"""
    auto = os.environ.get(AUTO_UPDATE_ENV, "").strip().lower()
    pinned = "uvx gns3-mcp@latest configure <agent> --yes, then restart the agent"
    if auto in ("1", "true", "yes", "on"):
        return "Restart the agent (or reconnect the gns3 MCP server): it runs gns3-mcp@latest."
    if auto in ("0", "false", "no", "off"):
        return f"Pinned install: {pinned}."
    return (
        "gns3-mcp@latest in the MCP config: restart the agent. "
        f"Pinned (gns3-mcp@<version>): {pinned}. "
        "Claude plugin: claude plugin update gns3-lab@gns3-mcp. "
        "Docker: docker compose pull && docker compose up -d. "
        "Claude Desktop extension: install the new .mcpb from the GitHub release."
    )


async def update_notice(installed: str, window: float = CHECK_WINDOW) -> dict | None:
    """{"installed", "latest", "how_to_update"} when PyPI has a newer release, else None"""
    latest = await latest_version(window)
    if not latest or not is_newer(latest, installed):
        return None
    return {"installed": installed, "latest": latest, "how_to_update": how_to_update()}
