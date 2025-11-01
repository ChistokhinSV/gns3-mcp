# GNS3 MCP Project Automation
# Run 'just' to see available commands

set dotenv-load := true
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# List all available recipes
default:
    @just --list

# Install all dependencies
install:
    pip install -r requirements.txt
    pip install -e .
    just install-lib

# Install bundled dependencies for .mcpb desktop extension
install-lib:
    powershell -Command "if (Test-Path mcp-server/lib) { Remove-Item -Path mcp-server/lib -Recurse -Force }"
    powershell -Command "New-Item -Path mcp-server/lib -ItemType Directory -Force | Out-Null"
    pip install --target=mcp-server/lib fastmcp>=2.13.0.2 fastapi>=0.115.0 httpx>=0.28.1 telnetlib3>=2.0.8 pydantic>=2.12.3 python-dotenv>=1.2.1 cairosvg>=2.8.2 docker>=7.1.0 tabulate>=0.9.0 --no-warn-script-location --quiet

# Run unit tests
test *ARGS='':
    pytest tests/unit -v --tb=short --cov=gns3_mcp --cov-report=term-missing {{ ARGS }}

# Run all tests (including integration)
test-all:
    pytest tests/ -v --tb=short --cov=gns3_mcp --cov-report=term-missing

# Lint code (with auto-fix)
lint:
    ruff check gns3_mcp/ --fix
    ruff check tests/ --fix

# Lint without fixes (CI mode)
lint-check:
    ruff check gns3_mcp/
    ruff check tests/

# Format code
format:
    ruff format gns3_mcp/
    ruff format tests/
    black gns3_mcp/
    black tests/

# Check formatting without changes (CI mode)
format-check:
    ruff format --check gns3_mcp/
    ruff format --check tests/
    black --check gns3_mcp/
    black --check tests/

# Type check with mypy (non-blocking - lenient mode)
type-check:
    -mypy gns3_mcp/
    @echo "[INFO] Mypy check complete (non-blocking in dev mode)"

# Clean build artifacts and caches
clean:
    powershell -Command "if (Test-Path mcp-server/lib) { Remove-Item -Path mcp-server/lib -Recurse -Force }"
    powershell -Command "if (Test-Path mcp-server/gns3_mcp) { Remove-Item -Path mcp-server/gns3_mcp -Recurse -Force }"
    powershell -Command "if (Test-Path mcp-server/mcp-server.mcpb) { Remove-Item -Path mcp-server/mcp-server.mcpb -Force }"
    powershell -Command "if (Test-Path dist) { Remove-Item -Path dist -Recurse -Force }"
    powershell -Command "Get-ChildItem -Path . -Include __pycache__,*.pyc,*.egg-info,.pytest_cache,.ruff_cache,.mypy_cache -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"

# Build desktop extension (.mcpb)
build: install-lib
    @echo "Copying source code to mcp-server for packaging..."
    powershell -Command "if (Test-Path mcp-server/gns3_mcp) { Remove-Item -Path mcp-server/gns3_mcp -Recurse -Force }"
    powershell -Command "Copy-Item -Path gns3_mcp -Destination mcp-server/gns3_mcp -Recurse -Force"
    @echo "Cleaning __pycache__ directories before packaging..."
    powershell -Command "Get-ChildItem -Path mcp-server -Include __pycache__ -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
    @echo "Building .mcpb package..."
    powershell -Command "cd mcp-server; npx @anthropic-ai/mcpb@1.1.2 pack"
    @echo "Built: mcp-server/mcp-server.mcpb"

# Validate manifest.json
validate-manifest:
    powershell -Command "cd mcp-server; npx @anthropic-ai/mcpb@1.1.2 validate manifest.json"

# Check version consistency across files
version-check:
    python scripts/check_version.py

# Check changelog contains current version
changelog-check:
    python scripts/check_changelog.py

# Bump version (major/minor/patch) across all files
# Usage: just bump patch | just bump minor | just bump major
# For dry-run: python scripts/bump_version.py patch --dry-run
bump level:
    python scripts/bump_version.py {{level}}

# Run all quality checks (local development mode - with auto-fixes)
check: lint format type-check test version-check changelog-check
    @echo "✓ All checks passed!"

# Run all checks in CI mode (strict, no auto-fixes)
ci: lint-check format-check type-check test version-check changelog-check
    @echo "✓ CI checks passed!"

# Run pre-commit hooks manually
pre-commit:
    pre-commit run --all-files

# Update pre-commit hooks
update-hooks:
    pre-commit autoupdate

# Full release pipeline
release: version-check changelog-check clean install check build validate-manifest
    @echo "✓ Release build complete!"
    @echo ""
    @echo "Next steps:"
    @echo "  1. Test .mcpb: Double-click mcp-server/mcp-server.mcpb"
    @echo "  2. Create tag: git tag -a v$(python scripts/get_version.py) -m 'Release v$(python scripts/get_version.py)'"
    @echo "  3. Push tag: git push origin v$(python scripts/get_version.py)"

# Show current version
version:
    python scripts/get_version.py

# Start MCP server locally for testing (HTTP mode)
dev-server:
    gns3-mcp --transport http --http-port 8100

# Start MCP server locally for testing (STDIO mode)
dev-stdio:
    gns3-mcp

# Install .mcpb in Claude Desktop (opens file)
install-desktop:
    powershell -Command "Start-Process 'mcp-server/mcp-server.mcpb'"

# Run Windows service management commands
service-install:
    .\server.cmd install

service-start:
    .\server.cmd start

service-stop:
    .\server.cmd stop

service-restart:
    .\server.cmd restart

service-status:
    .\server.cmd status

# Rebuild venv and lib folder
venv-rebuild:
    .\server.cmd venv-recreate
