"""Unit tests for dependency injection container (v0.50.0, GM-46)

Tests service registration, retrieval, lifetimes, and thread safety.
"""

import threading
from abc import ABC, abstractmethod
from typing import List

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "gns3_mcp" / "server"))

from di_container import Dependencies, ServiceLifetime


# ===== Test Interfaces and Implementations =====


class ITestService(ABC):
    """Test service interface"""

    @abstractmethod
    def get_value(self) -> str:
        pass


class TestServiceImpl(ITestService):
    """Test service implementation"""

    def __init__(self, value: str = "default"):
        self.value = value
        self.instance_id = id(self)

    def get_value(self) -> str:
        return self.value


class ICounter(ABC):
    """Counter service interface"""

    @abstractmethod
    def increment(self) -> int:
        pass

    @abstractmethod
    def get_count(self) -> int:
        pass


class Counter(ICounter):
    """Counter implementation"""

    def __init__(self):
        self.count = 0

    def increment(self) -> int:
        self.count += 1
        return self.count

    def get_count(self) -> int:
        return self.count


# ===== Container Initialization Tests =====


class TestContainerInitialization:
    """Tests for Dependencies container initialization"""

    def test_empty_container_initialization(self):
        """Test creating an empty container"""
        deps = Dependencies()
        assert deps is not None
        assert deps.registered_services() == []

    def test_has_method_returns_false_for_unregistered(self):
        """Test has() returns False for unregistered services"""
        deps = Dependencies()
        assert not deps.has(ITestService)


# ===== Singleton Service Tests =====


class TestSingletonServices:
    """Tests for singleton service lifetime"""

    def test_register_singleton(self):
        """Test registering a singleton service"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("test"))

        assert deps.has(ITestService)
        assert ITestService.__name__ in deps.registered_services()

    def test_singleton_returns_same_instance(self):
        """Test singleton returns the same instance on multiple calls"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("test"))

        # Get the service twice
        service1 = deps.get(ITestService)
        service2 = deps.get(ITestService)

        # Should be the exact same instance
        assert service1 is service2
        assert service1.instance_id == service2.instance_id

    def test_singleton_lazy_initialization(self):
        """Test singleton is not created until first get() call"""
        deps = Dependencies()
        creation_count = [0]  # Use list to avoid closure issues

        def factory():
            creation_count[0] += 1
            return TestServiceImpl(f"instance_{creation_count[0]}")

        deps.register_singleton(ITestService, factory)

        # Factory not called yet
        assert creation_count[0] == 0

        # First get() triggers creation
        service1 = deps.get(ITestService)
        assert creation_count[0] == 1

        # Second get() reuses instance
        service2 = deps.get(ITestService)
        assert creation_count[0] == 1  # Still 1, no new creation
        assert service1 is service2

    def test_singleton_thread_safety(self):
        """Test singleton creation is thread-safe"""
        deps = Dependencies()
        creation_count = [0]
        created_instances: List[TestServiceImpl] = []

        def factory():
            creation_count[0] += 1
            import time

            time.sleep(0.01)  # Simulate slow creation
            instance = TestServiceImpl(f"instance_{creation_count[0]}")
            created_instances.append(instance)
            return instance

        deps.register_singleton(ITestService, factory)

        # Create 10 threads that all try to get the service
        threads = []
        results: List[ITestService] = [None] * 10  # type: ignore

        def get_service(index: int):
            results[index] = deps.get(ITestService)

        for i in range(10):
            t = threading.Thread(target=get_service, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All threads should get the same instance
        first_instance = results[0]
        for result in results:
            assert result is first_instance

        # Factory should only be called once despite concurrent access
        assert creation_count[0] == 1


# ===== Transient Service Tests =====


class TestTransientServices:
    """Tests for transient service lifetime"""

    def test_register_transient(self):
        """Test registering a transient service"""
        deps = Dependencies()
        deps.register_transient(ITestService, lambda: TestServiceImpl("test"))

        assert deps.has(ITestService)

    def test_transient_returns_new_instance(self):
        """Test transient returns different instances on each call"""
        deps = Dependencies()
        deps.register_transient(ITestService, lambda: TestServiceImpl("test"))

        # Get the service twice
        service1 = deps.get(ITestService)
        service2 = deps.get(ITestService)

        # Should be different instances
        assert service1 is not service2
        assert service1.instance_id != service2.instance_id
        assert service1.value == service2.value  # Same value though

    def test_transient_creates_on_every_get(self):
        """Test transient creates new instance on every get() call"""
        deps = Dependencies()
        creation_count = [0]

        def factory():
            creation_count[0] += 1
            return TestServiceImpl(f"instance_{creation_count[0]}")

        deps.register_transient(ITestService, factory)

        # Each get() should create a new instance
        service1 = deps.get(ITestService)
        assert creation_count[0] == 1
        assert service1.value == "instance_1"

        service2 = deps.get(ITestService)
        assert creation_count[0] == 2
        assert service2.value == "instance_2"

        service3 = deps.get(ITestService)
        assert creation_count[0] == 3
        assert service3.value == "instance_3"


# ===== Instance Registration Tests =====


class TestInstanceRegistration:
    """Tests for pre-created instance registration"""

    def test_register_instance(self):
        """Test registering a pre-created instance"""
        deps = Dependencies()
        instance = TestServiceImpl("pre-created")
        deps.register_instance(ITestService, instance)

        assert deps.has(ITestService)

    def test_instance_returns_same_object(self):
        """Test instance registration returns the same object"""
        deps = Dependencies()
        instance = TestServiceImpl("pre-created")
        deps.register_instance(ITestService, instance)

        # Get the service
        retrieved = deps.get(ITestService)

        # Should be the exact same object
        assert retrieved is instance
        assert retrieved.instance_id == instance.instance_id

    def test_instance_available_immediately(self):
        """Test instance is available immediately (no lazy init)"""
        deps = Dependencies()
        instance = TestServiceImpl("immediate")
        deps.register_instance(ITestService, instance)

        # Should be able to get it right away
        retrieved = deps.get(ITestService)
        assert retrieved is instance


# ===== Multiple Services Tests =====


class TestMultipleServices:
    """Tests for managing multiple services"""

    def test_register_multiple_services(self):
        """Test registering multiple different services"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("test"))
        deps.register_singleton(ICounter, lambda: Counter())

        assert deps.has(ITestService)
        assert deps.has(ICounter)
        assert len(deps.registered_services()) == 2

    def test_get_multiple_services_independently(self):
        """Test getting multiple services independently"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("test"))
        deps.register_singleton(ICounter, lambda: Counter())

        # Get different services
        service = deps.get(ITestService)
        counter = deps.get(ICounter)

        assert isinstance(service, TestServiceImpl)
        assert isinstance(counter, Counter)
        assert service.get_value() == "test"
        assert counter.get_count() == 0

    def test_mixed_lifetimes(self):
        """Test mixing singleton and transient services"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("singleton"))
        deps.register_transient(ICounter, lambda: Counter())

        # Singleton should return same instance
        service1 = deps.get(ITestService)
        service2 = deps.get(ITestService)
        assert service1 is service2

        # Transient should return different instances
        counter1 = deps.get(ICounter)
        counter2 = deps.get(ICounter)
        assert counter1 is not counter2


# ===== Error Handling Tests =====


class TestErrorHandling:
    """Tests for error cases"""

    def test_get_unregistered_service_raises_keyerror(self):
        """Test getting unregistered service raises KeyError"""
        deps = Dependencies()

        with pytest.raises(KeyError) as exc_info:
            deps.get(ITestService)

        assert "not registered" in str(exc_info.value).lower()
        assert "ITestService" in str(exc_info.value)

    def test_error_message_shows_available_services(self):
        """Test error message lists available services"""
        deps = Dependencies()
        deps.register_singleton(ICounter, lambda: Counter())

        with pytest.raises(KeyError) as exc_info:
            deps.get(ITestService)

        error_msg = str(exc_info.value)
        assert "ICounter" in error_msg  # Shows what IS available


# ===== Container Management Tests =====


class TestContainerManagement:
    """Tests for container lifecycle management"""

    def test_clear_removes_all_services(self):
        """Test clear() removes all registered services"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("test"))
        deps.register_singleton(ICounter, lambda: Counter())

        assert len(deps.registered_services()) == 2

        deps.clear()

        assert len(deps.registered_services()) == 0
        assert not deps.has(ITestService)
        assert not deps.has(ICounter)

    def test_registered_services_returns_names(self):
        """Test registered_services() returns interface names"""
        deps = Dependencies()
        deps.register_singleton(ITestService, lambda: TestServiceImpl("test"))
        deps.register_singleton(ICounter, lambda: Counter())

        services = deps.registered_services()

        assert "ITestService" in services
        assert "ICounter" in services
        assert len(services) == 2


# ===== Integration Tests =====


class TestDIContainerIntegration:
    """Integration tests for realistic usage scenarios"""

    def test_typical_app_context_scenario(self):
        """Test DI container in app context scenario (GM-46)"""
        deps = Dependencies()

        # Register core services (like in app.py)
        gns3_mock = TestServiceImpl("gns3-client")
        console_mock = Counter()

        deps.register_instance(ITestService, gns3_mock)  # GNS3Client
        deps.register_instance(ICounter, console_mock)  # ConsoleManager

        # Retrieve services
        gns3 = deps.get(ITestService)
        console = deps.get(ICounter)

        assert gns3 is gns3_mock
        assert console is console_mock
        assert gns3.get_value() == "gns3-client"

    def test_shutdown_cleans_up_properly(self):
        """Test container cleanup during app shutdown"""
        deps = Dependencies()

        # Register services
        service = TestServiceImpl("test")
        deps.register_instance(ITestService, service)
        deps.register_singleton(ICounter, lambda: Counter())

        # Verify services are registered
        assert len(deps.registered_services()) == 2

        # Simulate shutdown
        deps.clear()

        # Container should be empty
        assert len(deps.registered_services()) == 0

        # Should not be able to get services anymore
        with pytest.raises(KeyError):
            deps.get(ITestService)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
