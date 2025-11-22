FROM python:3.13-slim

WORKDIR /app

# Install system packages required for dependencies
# - cairo libraries for cairosvg (topology diagram rendering)
# - curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager for faster dependency installation
RUN pip install --no-cache-dir uv

# Copy requirements and install production dependencies only
COPY mcp-server/requirements.txt .
RUN uv pip install --system \
    fastmcp>=2.13.0.2 \
    fastapi>=0.115.0 \
    httpx>=0.28.1 \
    telnetlib3>=2.0.8 \
    pydantic>=2.12.3 \
    python-dotenv>=1.2.1 \
    cairosvg>=2.8.2 \
    docker>=7.1.0 \
    tabulate>=0.9.0 \
    uvicorn[standard]>=0.34.0

# Copy application code and setup
COPY gns3_mcp/ ./gns3_mcp/
COPY pyproject.toml ./
COPY README.md ./

# Install the package in editable mode to get CLI entry point
RUN uv pip install --system -e .

# Expose MCP HTTP server port
EXPOSE 8000

# Environment variables with defaults
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8000
ENV LOG_LEVEL=INFO
ENV GNS3_PORT=80
ENV GNS3_USE_HTTPS=false
ENV GNS3_VERIFY_SSL=false

# Health check - verify server is listening and responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -s http://localhost:${HTTP_PORT}/ > /dev/null || exit 1

# Run MCP server in HTTP mode using CLI entry point
CMD ["gns3-mcp", "--transport", "http", "--http-host", "0.0.0.0"]
