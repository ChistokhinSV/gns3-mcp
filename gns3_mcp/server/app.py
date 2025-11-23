"""Application Lifecycle Management

Handles server startup, shutdown, background tasks, and AppContext.

v0.49.0: Extracted from main.py for better modularity (GM-45)
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict

from console_manager import ConsoleManager
from di_container import Dependencies
from fastmcp import FastMCP
from gns3_client import GNS3Client
from interfaces import IAppContext, IConsoleManager, IGns3Client, IResourceManager
from resources import ResourceManager

logger = logging.getLogger(__name__)


@dataclass
class AppContext(IAppContext):
    """Application context with GNS3 client, console manager, and resource manager

    v0.50.0: Added dependencies container for proper DI (GM-46)
    v0.53.3: Fixed interface implementation - use properties for lifecycle-managed fields
    """

    # Required fields (no defaults) must come first in dataclasses
    # IMPORTANT: Python dataclasses require all fields without defaults to appear before
    # fields with defaults. Using field() for required fields ensures proper ordering,
    # even though field() without arguments is functionally equivalent to no field() at all.
    # This is a workaround for Python's dataclass field ordering validation.
    # See: https://docs.python.org/3/library/dataclasses.html#mutable-default-values
    gns3: GNS3Client = field()
    console: ConsoleManager = field()
    dependencies: Dependencies = field()  # v0.50.0: DI container (GM-46)

    # Optional fields (with defaults) come after required fields
    # Private fields for properties
    _resource_manager: ResourceManager | None = field(default=None, init=False, repr=False)
    _current_project_id: str | None = field(default=None, init=False, repr=False)

    cleanup_task: asyncio.Task | None = field(default=None)
    # v0.38.0: Background authentication task (non-blocking startup)
    auth_task: asyncio.Task | None = field(default=None)
    # v0.26.0: Multi-proxy SSH support - maps node_name to proxy_url for routing
    ssh_proxy_mapping: Dict[str, str] = field(default_factory=dict)

    @property
    def resource_manager(self) -> ResourceManager | None:
        """Get resource manager (may be None during initialization)"""
        return self._resource_manager

    @resource_manager.setter
    def resource_manager(self, value: ResourceManager | None) -> None:
        """Set resource manager"""
        self._resource_manager = value

    @property
    def current_project_id(self) -> str | None:
        """Get current project ID (None if no project open)"""
        return self._current_project_id

    @current_project_id.setter
    def current_project_id(self, value: str | None) -> None:
        """Set current project ID"""
        self._current_project_id = value


async def periodic_console_cleanup(console: ConsoleManager):
    """Periodically clean up expired console sessions"""
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            await console.cleanup_expired()
            logger.debug("Completed periodic console cleanup")
        except asyncio.CancelledError:
            logger.info("Console cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


async def background_authentication(gns3: GNS3Client, context: AppContext):
    """Background task for GNS3 authentication with exponential backoff

    v0.38.0: Non-blocking authentication that allows server to start immediately
    Retries with exponential backoff: 5s → 10s → 30s → 60s → 300s (max)
    Updates connection status and auto-detects opened project on success
    """
    retry_delays = [5, 10, 30, 60, 300]  # Exponential backoff in seconds
    retry_index = 0

    while True:
        try:
            # Attempt authentication with 3-second timeout per attempt
            success = await gns3.authenticate(retry=False, retry_interval=3, max_retries=1)

            if success:
                logger.info("Background authentication succeeded")

                # Auto-detect opened project
                try:
                    projects = await gns3.get_projects()
                    opened = [p for p in projects if p.get("status") == "opened"]
                    if opened:
                        context.current_project_id = opened[0]["project_id"]
                        logger.info(f"Auto-detected opened project: {opened[0]['name']}")
                    else:
                        logger.info("No opened project found")
                except Exception as e:
                    logger.warning(f"Failed to detect opened project: {e}")

                # Reset backoff on success
                retry_index = 0

                # Wait 5 minutes before next check (keep-alive)
                await asyncio.sleep(300)
            else:
                # Failed - use exponential backoff
                delay = retry_delays[min(retry_index, len(retry_delays) - 1)]
                logger.warning(f"Background authentication failed: {gns3.connection_error}")
                logger.info(f"Retrying in {delay} seconds...")
                retry_index += 1
                await asyncio.sleep(delay)

        except asyncio.CancelledError:
            logger.info("Background authentication task cancelled")
            break
        except Exception as e:
            # Unexpected error - log and retry with current backoff
            logger.error(f"Error in background authentication: {e}")
            delay = retry_delays[min(retry_index, len(retry_delays) - 1)]
            await asyncio.sleep(delay)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle"""

    # Get server args
    args = server.get_args()

    # Read password from environment with fallback (CWE-214 fix - no password in process args)
    password = args.password or os.getenv("PASSWORD") or os.getenv("GNS3_PASSWORD")
    if not password:
        raise ValueError("Password required: use --password arg or PASSWORD/GNS3_PASSWORD env var")

    # Read HTTPS settings from environment if not provided as arguments
    use_https = args.use_https or os.getenv("GNS3_USE_HTTPS", "").lower() == "true"
    verify_ssl = args.verify_ssl
    if os.getenv("GNS3_VERIFY_SSL", "").lower() == "false":
        verify_ssl = False

    # Initialize GNS3 client
    gns3 = GNS3Client(
        host=args.host,
        port=args.port,
        username=args.username,
        password=password,
        use_https=use_https,
        verify_ssl=verify_ssl,
    )

    # Initialize console manager first (no dependencies)
    console = ConsoleManager()

    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(periodic_console_cleanup(console))

    # v0.50.0: Create DI container and register services (GM-46)
    dependencies = Dependencies()
    dependencies.register_instance(IGns3Client, gns3)
    dependencies.register_instance(IConsoleManager, console)
    logger.info(f"Registered services: {', '.join(dependencies.registered_services())}")

    # v0.38.0: Create context first (background auth needs it)
    # Server starts immediately without waiting for authentication
    context = AppContext(
        gns3=gns3,
        console=console,
        dependencies=dependencies,
        cleanup_task=cleanup_task,
    )
    # current_project_id will be set by background auth task (property defaults to None)

    # Register AppContext itself in DI container
    dependencies.register_instance(IAppContext, context)

    # Start background authentication task (non-blocking)
    auth_task = asyncio.create_task(background_authentication(gns3, context))
    context.auth_task = auth_task
    logger.info("Background authentication task started - server ready")

    # Initialize resource manager (needs context for callbacks)
    context.resource_manager = ResourceManager(context)
    dependencies.register_instance(IResourceManager, context.resource_manager)

    # Import and set global app for static resources
    from context import set_app

    set_app(context)

    try:
        yield context
    finally:
        # Import and clear global on shutdown
        from context import clear_app

        clear_app()

        # v0.50.0: Clear DI container (GM-46)
        dependencies.clear()
        logger.info("Cleared DI container")

        # Cleanup background tasks
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        if auth_task:
            auth_task.cancel()
            try:
                await auth_task
            except asyncio.CancelledError:
                pass

        await console.close_all()
        await gns3.close()

        logger.info("GNS3 MCP Server shutdown complete")
