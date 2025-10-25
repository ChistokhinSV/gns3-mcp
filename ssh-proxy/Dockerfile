FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY server/ ./server/

# Expose SSH proxy port
EXPOSE 8022

# Environment variables (can be overridden)
ENV API_PORT=8022
ENV LOG_LEVEL=INFO
ENV MAX_BUFFER_SIZE=10485760
ENV TRIM_BUFFER_SIZE=5242880
ENV MAX_HISTORY_JOBS=1000

# Run FastAPI with uvicorn
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8022"]
