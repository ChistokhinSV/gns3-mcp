"""Data Caching for GNS3 API

Simple TTL-based cache to reduce API calls and improve performance.
Cache is invalidated after mutations (node state changes, link changes, etc.)
"""

from typing import Dict, List, Any, Optional, TypeVar, Callable
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry:
    """Single cache entry with TTL"""

    def __init__(self, data: Any, ttl_seconds: int):
        """Initialize cache entry

        Args:
            data: Data to cache
            ttl_seconds: Time-to-live in seconds
        """
        self.data = data
        self.created_at = datetime.now()
        self.ttl = timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        """Check if entry has expired

        Returns:
            True if expired, False otherwise
        """
        age = datetime.now() - self.created_at
        return age > self.ttl

    def get(self) -> Any:
        """Get cached data

        Returns:
            Cached data or None if expired
        """
        if self.is_expired():
            return None
        return self.data


class DataCache:
    """TTL-based cache for GNS3 API data"""

    def __init__(self,
                 node_ttl: int = 30,
                 link_ttl: int = 30,
                 project_ttl: int = 60):
        """Initialize cache

        Args:
            node_ttl: TTL for node data in seconds
            link_ttl: TTL for link data in seconds
            project_ttl: TTL for project data in seconds
        """
        self.node_ttl = node_ttl
        self.link_ttl = link_ttl
        self.project_ttl = project_ttl

        # Cache storage: {project_id: CacheEntry}
        self._node_cache: Dict[str, CacheEntry] = {}
        self._link_cache: Dict[str, CacheEntry] = {}

        # Project list cache (no project_id key)
        self._project_cache: Optional[CacheEntry] = None

        # Lock for thread-safe access
        self._lock = asyncio.Lock()

        # Statistics
        self.stats = {
            "node_hits": 0,
            "node_misses": 0,
            "link_hits": 0,
            "link_misses": 0,
            "project_hits": 0,
            "project_misses": 0,
        }

    async def get_nodes(self,
                       project_id: str,
                       fetch_fn: Callable[[str], Any],
                       force_refresh: bool = False) -> List[Dict]:
        """Get nodes with caching

        Args:
            project_id: Project ID
            fetch_fn: Async function to fetch nodes if cache miss
            force_refresh: Force cache refresh

        Returns:
            List of node dictionaries
        """
        async with self._lock:
            # Check cache
            if not force_refresh and project_id in self._node_cache:
                cached_data = self._node_cache[project_id].get()
                if cached_data is not None:
                    self.stats["node_hits"] += 1
                    logger.debug(f"Node cache HIT for project {project_id}")
                    return cached_data

            # Cache miss - fetch fresh data
            self.stats["node_misses"] += 1
            logger.debug(f"Node cache MISS for project {project_id}")

            nodes = await fetch_fn(project_id)

            # Store in cache
            self._node_cache[project_id] = CacheEntry(nodes, self.node_ttl)

            return nodes

    async def get_links(self,
                       project_id: str,
                       fetch_fn: Callable[[str], Any],
                       force_refresh: bool = False) -> List[Dict]:
        """Get links with caching

        Args:
            project_id: Project ID
            fetch_fn: Async function to fetch links if cache miss
            force_refresh: Force cache refresh

        Returns:
            List of link dictionaries
        """
        async with self._lock:
            # Check cache
            if not force_refresh and project_id in self._link_cache:
                cached_data = self._link_cache[project_id].get()
                if cached_data is not None:
                    self.stats["link_hits"] += 1
                    logger.debug(f"Link cache HIT for project {project_id}")
                    return cached_data

            # Cache miss - fetch fresh data
            self.stats["link_misses"] += 1
            logger.debug(f"Link cache MISS for project {project_id}")

            links = await fetch_fn(project_id)

            # Store in cache
            self._link_cache[project_id] = CacheEntry(links, self.link_ttl)

            return links

    async def get_projects(self,
                          fetch_fn: Callable[[], Any],
                          force_refresh: bool = False) -> List[Dict]:
        """Get projects with caching

        Args:
            fetch_fn: Async function to fetch projects if cache miss
            force_refresh: Force cache refresh

        Returns:
            List of project dictionaries
        """
        async with self._lock:
            # Check cache
            if not force_refresh and self._project_cache is not None:
                cached_data = self._project_cache.get()
                if cached_data is not None:
                    self.stats["project_hits"] += 1
                    logger.debug("Project cache HIT")
                    return cached_data

            # Cache miss - fetch fresh data
            self.stats["project_misses"] += 1
            logger.debug("Project cache MISS")

            projects = await fetch_fn()

            # Store in cache
            self._project_cache = CacheEntry(projects, self.project_ttl)

            return projects

    async def invalidate_nodes(self, project_id: Optional[str] = None):
        """Invalidate node cache

        Args:
            project_id: Project ID to invalidate, or None for all projects
        """
        async with self._lock:
            if project_id:
                if project_id in self._node_cache:
                    del self._node_cache[project_id]
                    logger.debug(f"Invalidated node cache for project {project_id}")
            else:
                self._node_cache.clear()
                logger.debug("Invalidated all node caches")

    async def invalidate_links(self, project_id: Optional[str] = None):
        """Invalidate link cache

        Args:
            project_id: Project ID to invalidate, or None for all projects
        """
        async with self._lock:
            if project_id:
                if project_id in self._link_cache:
                    del self._link_cache[project_id]
                    logger.debug(f"Invalidated link cache for project {project_id}")
            else:
                self._link_cache.clear()
                logger.debug("Invalidated all link caches")

    async def invalidate_projects(self):
        """Invalidate project cache"""
        async with self._lock:
            self._project_cache = None
            logger.debug("Invalidated project cache")

    async def invalidate_all(self):
        """Invalidate all caches"""
        async with self._lock:
            self._node_cache.clear()
            self._link_cache.clear()
            self._project_cache = None
            logger.debug("Invalidated all caches")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics

        Returns:
            Dictionary with cache hit/miss stats
        """
        total_node = self.stats["node_hits"] + self.stats["node_misses"]
        total_link = self.stats["link_hits"] + self.stats["link_misses"]
        total_project = self.stats["project_hits"] + self.stats["project_misses"]

        return {
            "nodes": {
                "hits": self.stats["node_hits"],
                "misses": self.stats["node_misses"],
                "total": total_node,
                "hit_rate": (self.stats["node_hits"] / total_node * 100) if total_node > 0 else 0
            },
            "links": {
                "hits": self.stats["link_hits"],
                "misses": self.stats["link_misses"],
                "total": total_link,
                "hit_rate": (self.stats["link_hits"] / total_link * 100) if total_link > 0 else 0
            },
            "projects": {
                "hits": self.stats["project_hits"],
                "misses": self.stats["project_misses"],
                "total": total_project,
                "hit_rate": (self.stats["project_hits"] / total_project * 100) if total_project > 0 else 0
            }
        }

    def reset_stats(self):
        """Reset cache statistics"""
        self.stats = {
            "node_hits": 0,
            "node_misses": 0,
            "link_hits": 0,
            "link_misses": 0,
            "project_hits": 0,
            "project_misses": 0,
        }
