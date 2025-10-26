# GNS3 MCP - Known Issues and Improvements

This file tracks issues, bugs, and improvement opportunities for the GNS3 MCP server and SSH proxy.

## Active Issues

### [CRITICAL] SSH Proxy: Stale Session Management
**Discovered**: 2025-10-25
**Affects**: SSH Proxy v0.1.5
**Severity**: High - Breaks all SSH functionality after lab restart

#### Problem
SSH sessions persist in memory with closed sockets after lab restart, causing all SSH commands to fail with "Socket is closed" error. Sessions are not automatically cleaned up when underlying connections die.

#### Symptoms
- `ssh_command()` returns `completed: false` with empty output
- Execution time exactly ~1 second (timeout)
- Logs show: `ERROR - Command failed: Socket is closed`
- Same session_id reused even for "new" connections
- Prompt detection fails: `Pattern not detected: '[\$\#]'`

#### Root Cause
1. SSH proxy maintains `_sessions` dict mapping `node_name → session_id`
2. When lab restarts, SSH connections close but sessions persist in dict
3. `ssh_configure()` finds existing session and returns it (reuses stale session)
4. `ssh_command()` attempts to use closed socket → fails immediately
5. No automatic detection or cleanup of dead sessions

#### Current Workaround
```bash
ssh gns3 "docker restart gns3-ssh-proxy"
```

#### Proposed Fixes

**Fix 1: Session Health Check**
- Before reusing session, verify socket is alive
- If socket closed, remove from `_sessions` and create new connection
- Implementation:
  ```python
  def _is_session_alive(self, session_id: str) -> bool:
      session = self._sessions.get(session_id)
      if not session or not session.connection:
          return False
      try:
          # Quick health check - send empty command
          session.connection.send_command("", expect_string=r".*")
          return True
      except Exception:
          return False
  ```

**Fix 2: Automatic Cleanup on Failure**
- When "Socket is closed" error occurs, automatically:
  1. Remove session from `_sessions` dict
  2. Log warning about stale session cleanup
  3. Optionally: Auto-retry with new connection
- Implementation location: `session_manager.py:send_command_adaptive()`

**Fix 3: Session TTL/Expiry**
- Add `last_used` timestamp to session metadata
- Cleanup sessions inactive for >30 minutes
- Implementation: Background task or lazy cleanup on access

**Fix 4: Force Recreation Parameter**
- Add `force=True` parameter to `ssh_configure()` MCP tool
- Allows manual override to create fresh session
- Example: `ssh_configure("A-DIST1", ..., force=True)`

**Fix 5: Better Error Messages**
- Return informative error instead of `completed: false` with empty output
- Example:
  ```json
  {
    "completed": false,
    "error": "SSH_CONNECTION_FAILED",
    "error_code": "SSH_DISCONNECTED",
    "details": "Socket is closed - connection terminated",
    "suggested_action": "Session may be stale. Try ssh_disconnect() then reconfigure."
  }
  ```

#### Priority
**HIGH** - This breaks all SSH automation after every lab restart/reboot

#### Estimated Effort
- Fix 1 (Health Check): 2 hours
- Fix 2 (Auto Cleanup): 1 hour
- Fix 3 (TTL): 2 hours
- Fix 4 (Force param): 30 minutes
- Fix 5 (Error messages): 1 hour
- **Total**: ~6.5 hours

#### Testing Required
1. Start lab, configure SSH sessions for all DIST nodes
2. Restart lab (nodes restart, SSH sessions die)
3. Verify old sessions detected as dead
4. Verify `ssh_configure()` creates new sessions automatically
5. Verify `ssh_command()` works after lab restart
6. Verify error messages are informative

---

## Future Enhancements

_(Add more issues as discovered)_
