#!/bin/bash
set -e

# Create TFTP directory if it doesn't exist (handles mounted volumes)
mkdir -p /opt/gns3-ssh-proxy/tftp
chmod 777 /opt/gns3-ssh-proxy/tftp

# Start supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
