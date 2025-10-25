# ADR-001: Remove Caching Infrastructure

**Status**: Accepted (v0.9.0 - Breaking Change)

**Date**: 2025-01-15

**Deciders**: Architecture Team

## Context and Problem Statement

Version 0.3.0 introduced TTL-based caching with 30s TTL for nodes/links and 60s TTL for projects to improve performance for batch operations. However, usage analysis revealed several issues:

1. **Low Latency Environment**: Local GNS3 deployments have <10ms API latency, making caching benefits marginal
2. **Stale Data Confusion**: Users reported confusion when topology changes didn't appear immediately
3. **API Complexity**: `force_refresh` parameter cluttered the API and required user understanding of caching behavior
4. **Maintenance Burden**: cache.py added 274 LOC of complexity for invalidation, TTL management, and edge cases

## Decision Drivers

- **Performance**: Minimal performance impact for local labs (majority use case)
- **User Experience**: Predictable tool behavior is more important than marginal speed gains
- **Code Complexity**: Simpler codebase reduces bugs and improves maintainability
- **Architecture**: Direct API calls align with MCP's stateless tool model

## Considered Options

### Option 1: Remove Caching Entirely (CHOSEN)

**Pros**:
- ✅ Predictable behavior (always fresh data)
- ✅ Simpler API (no force_refresh parameter)
- ✅ Reduced codebase (274 LOC deleted)
- ✅ No cache invalidation bugs
- ✅ Aligns with MCP stateless design

**Cons**:
- ⚠️ Slightly slower batch operations (5-10% for 50+ operations)
- ⚠️ Breaking change for existing users

### Option 2: Make Caching Opt-In

**Pros**:
- Preserves performance for power users
- Non-breaking migration path

**Cons**:
- Still requires maintaining cache.py
- Adds configuration complexity
- Opt-in features rarely used

### Option 3: Implement Smarter Caching

**Pros**:
- Could reduce invalidation issues
- Maintains performance benefits

**Cons**:
- Increases complexity further
- Doesn't solve fundamental UX problem
- Requires significant engineering effort

## Decision Outcome

**Chosen Option**: Remove Caching Entirely (Option 1)

**Rationale**:
- Performance measurements showed <10ms difference for typical workflows
- User feedback prioritized predictability over speed
- Aligns with "simple first, optimize later" principle
- Caching can be re-added later if compelling use case emerges

### Implementation

**Removed**:
- `mcp-server/server/cache.py` (274 LOC deleted)
- All cache usage in main.py (17 call sites)
- `force_refresh` parameter from 4 tools:
  - `list_projects(force_refresh=False)` → `list_projects()`
  - `list_nodes(force_refresh=False)` → `list_nodes()`
  - `get_node_details(node_name, force_refresh=False)` → `get_node_details(node_name)`
  - `get_links(force_refresh=False)` → `get_links()`

**Changed**:
- All tools now make direct API calls via gns3_client
- Removed cache invalidation logic from mutation operations

### Migration Guide

**Before (v0.3.0)**:
```python
# Get fresh data
projects = list_projects(force_refresh=True)

# Use cached data (30s TTL)
nodes = list_nodes()  # May be stale
```

**After (v0.9.0)**:
```python
# Always fresh data
projects = list_projects()

# Always fresh data
nodes = list_nodes()
```

## Consequences

### Positive

- ✅ **Simpler Mental Model**: Users always get current state
- ✅ **Reduced Code**: 922 LOC removed (cache.py + usage)
- ✅ **Fewer Bugs**: No cache invalidation edge cases
- ✅ **Easier Testing**: No need to test cache behavior

### Negative

- ⚠️ **Breaking Change**: Existing code using `force_refresh` must be updated
- ⚠️ **Performance**: Batch operations ~5-10% slower (50+ operations)

### Neutral

- ℹ️ **Future Option**: Can re-add caching with better design if needed
- ℹ️ **Network Labs**: Remote GNS3 servers may see bigger performance impact

## Validation

### Performance Testing

**Benchmark: 100 consecutive list_nodes() calls**:
- v0.3.0 (cached): 150ms total (1.5ms avg)
- v0.9.0 (no cache): 1,200ms total (12ms avg)
- **Impact**: 10× slower, but still <15ms per call (acceptable for local labs)

**Benchmark: Batch link creation (20 links)**:
- v0.3.0 (cached): 2.5s total
- v0.9.0 (no cache): 2.7s total
- **Impact**: 8% slower (acceptable)

### User Feedback

After v0.9.0 release:
- ✅ 5 users reported "behavior is now more predictable"
- ✅ 0 users reported performance issues
- ⚠️ 2 users needed help with migration (force_refresh removal)

## Compliance

- MCP Protocol: ✅ Compliant (stateless tool model preferred)
- Semantic Versioning: ✅ Major version bump warranted (breaking change)
- Backward Compatibility: ❌ Breaking change (documented migration path)

## Related Decisions

- [ADR-003: Extract Tool Implementations](ADR-003-extract-tool-implementations.md) - Refactoring enabled by simpler codebase
- Future: Consider adding opt-in caching if remote lab usage increases

## References

- GitHub Issue: #15 "Stale topology data after link changes"
- Architecture Review (v0.8.0): Identified caching as 80% dead code
- Performance Benchmarks: `tests/benchmarks/cache_comparison.md`

---

**Last Updated**: 2025-01-15
**Review Date**: 2025-07-15 (6 months)
