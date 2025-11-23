FROM python:3.13-slim

# Build argument to control ansible installation
ARG INSTALL_ANSIBLE=false

WORKDIR /app

# Install system packages and create directories in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    traceroute \
    iproute2 \
    net-tools \
    dnsutils \
    curl \
    openssh-client \
    tftpd-hpa \
    nginx \
    openssl \
    supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/gns3-ssh-proxy && chmod 755 /opt/gns3-ssh-proxy \
    && mkdir -p /opt/gns3-ssh-proxy/tftp && chmod 777 /opt/gns3-ssh-proxy/tftp \
    && openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
       -keyout /etc/nginx/proxy.key -out /etc/nginx/proxy.crt \
       -subj "/CN=gns3-ssh-proxy" \
    && mkdir -p /var/log/supervisor

# Copy and install base Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (most frequently changing layer)
COPY server/ ./server/

# Copy nginx and supervisor configurations
COPY config/nginx.conf /etc/nginx/sites-available/default
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports
EXPOSE 8022 69/udp

# Environment variables (can be overridden)
ENV API_PORT=8022
ENV LOG_LEVEL=INFO
ENV MAX_BUFFER_SIZE=10485760
ENV TRIM_BUFFER_SIZE=5242880
ENV MAX_HISTORY_JOBS=1000

# Run all services via supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
