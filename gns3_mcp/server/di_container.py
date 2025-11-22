"""Dependency Injection Container

Lightweight DI container for managing service dependencies and eliminating global state.

v0.50.0: Created for GM-46 - Dependency injection pattern
"""

import threading
from enum import Enum
from typing import Any, Callable, Dict, Generic, Type, TypeVar, cast

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime management strategies"""

    SINGLETON = "singleton"  # Created once, reused for all requests
    TRANSIENT = "transient"  # Created fresh for each request


class ServiceRegistration(Generic[T]):
    """Registration metadata for a service"""

    def __init__(
        self,
        interface: Type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime,
    ):
        """Initialize service registration

        Args:
            interface: Interface type (ABC) to register
            factory: Factory function to create instances
            lifetime: Service lifetime strategy
        """
        self.interface = interface
        self.factory = factory
        self.lifetime = lifetime
        self.instance: T | None = None  # Singleton instance cache


class Dependencies:
    """Dependency injection container

    Thread-safe service container with singleton and transient lifetime support.
    Replaces global state pattern with proper dependency management.

    Example:
        ```python
        # During app startup
        deps = Dependencies()
        deps.register_singleton(IGns3Client, lambda: GNS3Client(...))
        deps.register_singleton(IConsoleManager, lambda: ConsoleManager())

        # In tools/resources
        def my_tool(ctx: Context):
            deps: Dependencies = ctx.request_context.lifespan_context.dependencies
            gns3 = deps.get(IGns3Client)
            # Use gns3 client...
        ```
    """

    def __init__(self):
        """Initialize empty dependency container"""
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._lock = threading.Lock()

    def register_singleton(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a singleton service

        Singleton services are created once on first access and reused.
        Thread-safe: only one instance created even with concurrent access.

        Args:
            interface: Interface type to register (e.g., IGns3Client)
            factory: Function to create the service instance

        Example:
            ```python
            deps.register_singleton(
                IGns3Client,
                lambda: GNS3Client(host="localhost", port=80, ...)
            )
            ```
        """
        with self._lock:
            self._registrations[interface] = ServiceRegistration(
                interface=interface,
                factory=factory,
                lifetime=ServiceLifetime.SINGLETON,
            )

    def register_transient(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a transient service

        Transient services are created fresh on each `get()` call.
        Use for stateful services that shouldn't be shared.

        Args:
            interface: Interface type to register
            factory: Function to create new instances

        Example:
            ```python
            deps.register_transient(
                IReportGenerator,
                lambda: ReportGenerator()
            )
            ```
        """
        with self._lock:
            self._registrations[interface] = ServiceRegistration(
                interface=interface,
                factory=factory,
                lifetime=ServiceLifetime.TRANSIENT,
            )

    def register_instance(self, interface: Type[T], instance: T) -> None:
        """Register a pre-created singleton instance

        Useful for registering existing objects (e.g., AppContext created during startup).

        Args:
            interface: Interface type to register
            instance: Pre-created instance to use

        Example:
            ```python
            context = AppContext(gns3=..., console=...)
            deps.register_instance(IAppContext, context)
            ```
        """
        with self._lock:
            registration = ServiceRegistration(
                interface=interface,
                factory=lambda: instance,  # Factory returns the same instance
                lifetime=ServiceLifetime.SINGLETON,
            )
            registration.instance = instance  # Cache immediately
            self._registrations[interface] = registration

    def get(self, interface: Type[T]) -> T:
        """Get a service instance

        Thread-safe retrieval with lazy initialization for singletons.

        Args:
            interface: Interface type to retrieve

        Returns:
            Service instance

        Raises:
            KeyError: If service not registered

        Example:
            ```python
            gns3 = deps.get(IGns3Client)
            console = deps.get(IConsoleManager)
            ```
        """
        if interface not in self._registrations:
            raise KeyError(
                f"Service not registered: {interface.__name__}. "
                f"Available services: {', '.join(r.__name__ for r in self._registrations.keys())}"
            )

        registration = self._registrations[interface]

        if registration.lifetime == ServiceLifetime.SINGLETON:
            # Thread-safe singleton creation (double-check locking)
            if registration.instance is None:
                with self._lock:
                    if registration.instance is None:
                        registration.instance = registration.factory()
            return cast(T, registration.instance)
        else:
            # Transient: create new instance each time
            return registration.factory()

    def has(self, interface: Type) -> bool:
        """Check if service is registered

        Args:
            interface: Interface type to check

        Returns:
            True if registered, False otherwise
        """
        return interface in self._registrations

    def clear(self) -> None:
        """Clear all registrations

        Used during shutdown to release singleton instances.
        """
        with self._lock:
            self._registrations.clear()

    def registered_services(self) -> list[str]:
        """Get list of registered service names

        Returns:
            List of interface names (e.g., ['IGns3Client', 'IConsoleManager'])
        """
        return [iface.__name__ for iface in self._registrations.keys()]
