# Portable GNS3 MCP Service Setup

This guide explains how to set up the GNS3 MCP HTTP service that works from any folder location using `uvx` instead of traditional venv.

## Key Changes

### Before (v0.46.x and earlier)
- Used Python venv in fixed location
- Absolute paths in XML configuration
- Required .env file for service credentials

### After (v0.47.0+)
- Uses `uvx` for isolated package execution
- Relative paths using `%BASE%` variable
- Reads credentials from Windows environment variables
- .env file only for development mode

## Benefits

1. **Portable** - Works from any folder location
2. **No venv management** - uvx handles isolation automatically
3. **Cleaner** - No venv folder cluttering the project
4. **Secure** - Credentials stored in Windows environment (not .env)

## Prerequisites

1. **Python 3.10+** installed and in PATH
2. **uv/uvx** installed:
   ```bash
   pip install uv
   ```
3. **WinSW** - automatically downloaded by server.cmd

## Setup Instructions

### 1. Configure Credentials

You have two options:

#### Option A: Automated (Recommended)

Run the PowerShell script as Administrator:
```powershell
.\set-env-vars.ps1
```

This reads your .env file and sets system environment variables automatically.

For user-level variables only (no admin required):
```powershell
.\set-env-vars.ps1 -UserLevel
```

#### Option B: Manual

Set Windows environment variables manually (PowerShell as Admin):
```powershell
# Required variables
[Environment]::SetEnvironmentVariable("GNS3_USER", "admin", "Machine")
[Environment]::SetEnvironmentVariable("GNS3_PASSWORD", "your-password", "Machine")
[Environment]::SetEnvironmentVariable("GNS3_HOST", "192.168.1.20", "Machine")
[Environment]::SetEnvironmentVariable("GNS3_PORT", "80", "Machine")

# Optional variables (with defaults)
[Environment]::SetEnvironmentVariable("HTTP_HOST", "127.0.0.1", "Machine")
[Environment]::SetEnvironmentVariable("HTTP_PORT", "8100", "Machine")
[Environment]::SetEnvironmentVariable("LOG_LEVEL", "INFO", "Machine")
[Environment]::SetEnvironmentVariable("MCP_API_KEY", "your-key", "Machine")
[Environment]::SetEnvironmentVariable("GNS3_USE_HTTPS", "false", "Machine")
[Environment]::SetEnvironmentVariable("GNS3_VERIFY_SSL", "true", "Machine")
```

**Note**: Replace "Machine" with "User" to set user-level variables (no admin required).

### 2. Install Service

```bash
# Install and start service (requires admin)
.\server.cmd install

# Check status
.\server.cmd status
```

### 3. Verify Installation

```bash
# Check service is running
.\server.cmd status

# View logs
type GNS3-MCP-HTTP.wrapper.log
type mcp-http-server.log
```

## Usage

### Development Mode (Direct Run)

For development and testing, you can run the server directly without installing the service:

```bash
.\server.cmd run
```

This will:
1. Load credentials from .env file (if exists)
2. Run server using uvx
3. Display output in console

Press Ctrl+C to stop.

### Service Mode (Production)

Once installed as a service:

```bash
# Start service
.\server.cmd start

# Stop service
.\server.cmd stop

# Restart service
.\server.cmd restart

# Reinstall service (after updates)
.\server.cmd reinstall

# Uninstall service
.\server.cmd uninstall
```

### Create Service User (Optional)

For enhanced security, run the service as a low-privilege user:

```bash
.\server.cmd create-user
```

This creates a `GNS3MCPService` user account with minimal permissions.

## Moving the Folder

The service is now portable! To move to a different location:

1. **Stop the service** (if running):
   ```bash
   .\server.cmd stop
   ```

2. **Uninstall the service**:
   ```bash
   .\server.cmd uninstall
   ```

3. **Move the folder** to new location

4. **Reinstall the service** from new location:
   ```bash
   cd "path\to\new\location"
   .\server.cmd install
   ```

Environment variables remain intact, no need to reconfigure credentials.

## How It Works

### server.cmd
- Detects script directory dynamically: `%~dp0`
- Uses uvx to run package from current directory
- Loads .env in development mode only

### GNS3-MCP-HTTP.xml
- Uses `%BASE%` variable (set by WinSW to service directory)
- Reads credentials from Windows environment variables
- Calls `run-uvx.cmd` wrapper to locate uvx
- Portable to any folder location

### run-uvx.cmd (Wrapper Script)
Windows services don't inherit user PATH, so we use a wrapper that:
1. Searches for uvx.exe in common Python installation locations
2. Tries multiple Python versions (3.10-3.13)
3. Checks user and system-wide installations
4. Passes all arguments through to uvx

### uvx Execution
```bash
uvx --from "%BASE%" gns3-mcp --transport http --http-port 8100
```

This tells uvx to:
1. Look for package in `%BASE%` directory
2. Install it in isolated cache
3. Run with specified arguments

## Troubleshooting

### Service Won't Start

1. Check environment variables are set:
   ```powershell
   Get-ChildItem Env: | Where-Object { $_.Name -like "GNS3_*" }
   ```

2. Check uvx is in PATH:
   ```bash
   where uvx
   ```

3. Check logs:
   ```bash
   type GNS3-MCP-HTTP.wrapper.log
   ```

### uvx Not Found

Install uv:
```bash
pip install uv
```

Verify installation:
```bash
uvx --version
```

### Environment Variables Not Applied

After setting environment variables:
1. **Close all command prompts** (they cache environment)
2. **Open new command prompt** as Administrator
3. **Reinstall service**: `.\server.cmd reinstall`

### Permission Errors

If service fails to start:
1. Check service user has read access to folder
2. Check service user has write access for logs
3. Run: `.\server.cmd create-user` to set permissions

## Migration from v0.46.x

If you have an existing installation with venv:

1. **Stop and uninstall** old service:
   ```bash
   .\server.cmd stop
   .\server.cmd uninstall
   ```

2. **Set environment variables**:
   ```powershell
   .\set-env-vars.ps1
   ```

3. **Remove old venv** (optional):
   ```bash
   rmdir /s /q venv
   ```

4. **Install uv** (if not installed):
   ```bash
   pip install uv
   ```

5. **Install new service**:
   ```bash
   .\server.cmd install
   ```

6. **Verify**:
   ```bash
   .\server.cmd status
   ```

The .env file is now only used for development mode (`.\server.cmd run`).

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| GNS3_USER | GNS3 username | admin |
| GNS3_PASSWORD | GNS3 password | your-password |
| GNS3_HOST | GNS3 server IP/hostname | 192.168.1.20 |
| GNS3_PORT | GNS3 server port | 80 |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| HTTP_HOST | MCP HTTP bind address | 127.0.0.1 |
| HTTP_PORT | MCP HTTP port | 8100 |
| LOG_LEVEL | Logging level | INFO |
| MCP_API_KEY | MCP API authentication key | (auto-generated) |
| GNS3_USE_HTTPS | Use HTTPS for GNS3 | false |
| GNS3_VERIFY_SSL | Verify SSL certificates | true |

## Security Notes

1. **Credentials Location**:
   - Service: Windows environment variables (encrypted by OS)
   - Development: .env file (gitignored)

2. **Service User**:
   - Default: Runs as `GNS3MCPService` (low privilege)
   - Can be changed in GNS3-MCP-HTTP.xml

3. **API Key**:
   - Auto-generated if not set
   - Stored in environment variable
   - Used for MCP HTTP authentication

4. **Best Practices**:
   - Use Machine-level env vars for system service
   - Use User-level env vars for personal use
   - Never commit .env to git
   - Rotate passwords periodically

## Additional Resources

- [WinSW Documentation](https://github.com/winsw/winsw)
- [uv/uvx Documentation](https://github.com/astral-sh/uv)
- [GNS3 API Documentation](https://gns3-server.readthedocs.io/)
