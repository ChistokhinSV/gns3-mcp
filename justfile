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

# Install bundled dependencies for .mcpb desktop extension (DEPRECATED - using runtime venv instead)
# install-lib:
#     powershell -Command "if (Test-Path mcp-server/lib) { Remove-Item -Path mcp-server/lib -Recurse -Force }"
#     powershell -Command "New-Item -Path mcp-server/lib -ItemType Directory -Force | Out-Null"
#     pip install --target=mcp-server/lib fastmcp>=2.13.0.2 fastapi>=0.115.0 httpx>=0.28.1 telnetlib3>=2.0.8 pydantic>=2.12.3 python-dotenv>=1.2.1 cairosvg>=2.8.2 docker>=7.1.0 tabulate>=0.9.0 --no-warn-script-location --quiet

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

# Clean build artifacts and caches (keeps UV binary - permanent fixture)
clean:
    powershell -Command "if (Test-Path mcp-server/lib) { Remove-Item -Path mcp-server/lib -Recurse -Force }"
    powershell -Command "if (Test-Path mcp-server/venv) { Remove-Item -Path mcp-server/venv -Recurse -Force }"
    powershell -Command "if (Test-Path mcp-server/gns3_mcp) { Remove-Item -Path mcp-server/gns3_mcp -Recurse -Force }"
    powershell -Command "if (Test-Path mcp-server/requirements.txt) { Remove-Item -Path mcp-server/requirements.txt -Force }"
    powershell -Command "if (Test-Path mcp-server/mcp-server.mcpb) { Remove-Item -Path mcp-server/mcp-server.mcpb -Force }"
    powershell -Command "if (Test-Path dist) { Remove-Item -Path dist -Recurse -Force }"
    powershell -Command "Get-ChildItem -Path . -Include __pycache__,*.pyc,*.egg-info,.pytest_cache,.ruff_cache,.mypy_cache -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
    @echo "Note: mcp-server/uv.exe (58 MB) is kept - it's bundled in .mcpb"

# Build desktop extension (.mcpb) - using UV for fast runtime dependency installation
build:
    @echo "Checking for UV package manager binary..."
    powershell -Command "if (-not (Test-Path mcp-server/uv.exe)) { Write-Host 'ERROR: UV binary not found at mcp-server/uv.exe' -ForegroundColor Red; Write-Host 'Download from: https://github.com/astral-sh/uv/releases/latest' -ForegroundColor Yellow; exit 1 }"
    @echo "Copying source code to mcp-server for packaging..."
    powershell -Command "if (Test-Path mcp-server/gns3_mcp) { Remove-Item -Path mcp-server/gns3_mcp -Recurse -Force }"
    powershell -Command "Copy-Item -Path gns3_mcp -Destination mcp-server/gns3_mcp -Recurse -Force"
    @echo "Copying requirements.txt for runtime dependency installation..."
    powershell -Command "Copy-Item -Path requirements.txt -Destination mcp-server/requirements.txt -Force"
    @echo "Cleaning __pycache__ directories before packaging..."
    powershell -Command "Get-ChildItem -Path mcp-server -Include __pycache__ -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
    @echo "Building .mcpb package with UV binary (58 MB)..."
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

# ============================================================================
# Docker Commands
# ============================================================================

# Build Docker image locally
docker-build:
    docker build -t gns3-mcp:dev -t chistokhinsv/gns3-mcp:latest .

# Run Docker container locally (requires .env file)
docker-run:
    docker run --rm -it \
      --name gns3-mcp-dev \
      -p 8000:8000 \
      --env-file .env \
      gns3-mcp:dev

# Run Docker container in background
docker-run-bg:
    docker run -d \
      --name gns3-mcp-dev \
      -p 8000:8000 \
      --env-file .env \
      --restart unless-stopped \
      gns3-mcp:dev

# Stop and remove Docker container
docker-stop:
    docker stop gns3-mcp-dev || true
    docker rm gns3-mcp-dev || true

# Start docker-compose stack (MCP + SSH proxy)
docker-compose-up:
    docker-compose up -d

# Stop docker-compose stack
docker-compose-down:
    docker-compose down

# View docker-compose logs (follow mode)
docker-compose-logs service='':
    @if [ -z "{{service}}" ]; then \
        docker-compose logs -f; \
    else \
        docker-compose logs -f {{service}}; \
    fi

# Restart docker-compose services
docker-compose-restart:
    docker-compose restart

# Pull latest images and restart
docker-compose-update:
    docker-compose pull
    docker-compose up -d

# Test Docker container (health check)
docker-test:
    @echo "Testing Docker container health..."
    @echo ""
    @echo "1. Building image..."
    @just docker-build
    @echo ""
    @echo "2. Starting container..."
    @just docker-run-bg
    @echo ""
    @echo "3. Waiting for container to start..."
    @powershell -Command "Start-Sleep -Seconds 5"
    @echo ""
    @echo "4. Testing health endpoint..."
    @curl -f http://localhost:8000/health || echo "Health check failed!"
    @echo ""
    @echo "5. Stopping container..."
    @just docker-stop
    @echo ""
    @echo "Docker test complete!"

# Build and push Docker image to Docker Hub (requires login)
docker-push version='latest':
    docker build -t chistokhinsv/gns3-mcp:{{version}} .
    @if [ "{{version}}" != "latest" ]; then \
        docker tag chistokhinsv/gns3-mcp:{{version}} chistokhinsv/gns3-mcp:latest; \
    fi
    docker push chistokhinsv/gns3-mcp:{{version}}
    @if [ "{{version}}" != "latest" ]; then \
        docker push chistokhinsv/gns3-mcp:latest; \
    fi

# Multi-platform Docker build (requires buildx)
docker-build-multi version='latest':
    docker buildx build --platform linux/amd64,linux/arm64 \
      -t chistokhinsv/gns3-mcp:{{version}} \
      -t chistokhinsv/gns3-mcp:latest \
      --push .

# Clean Docker resources
docker-clean:
    docker stop gns3-mcp-dev || true
    docker rm gns3-mcp-dev || true
    docker-compose down || true
    docker image prune -f
