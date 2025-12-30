#!/bin/bash
# Lambda GPU Coding Stack - Cloud-init User Data Script
# This script runs on first boot to configure the instance
set -e

PERSISTENT="/lambda/nfs/coding-stack"
LOG="/var/log/gpu-stack-boot.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

log "GPU Stack boot starting"

# Wait for filesystem mount (max 5 minutes)
MOUNT_TIMEOUT=300
MOUNT_WAITED=0
while [ ! -d "$PERSISTENT" ]; do
    if [ $MOUNT_WAITED -ge $MOUNT_TIMEOUT ]; then
        log "ERROR: Filesystem not mounted after ${MOUNT_TIMEOUT}s"
        exit 1
    fi
    sleep 5
    MOUNT_WAITED=$((MOUNT_WAITED + 5))
    log "Waiting for filesystem mount... (${MOUNT_WAITED}s)"
done
log "Filesystem mounted at $PERSISTENT"

# Source secrets
if [ ! -f "$PERSISTENT/secrets/env.sh" ]; then
    log "ERROR: Secrets file not found"
    exit 1
fi
source "$PERSISTENT/secrets/env.sh"
log "Secrets loaded"

# Create symlinks
ln -sf "$PERSISTENT/n8n-data" /home/ubuntu/.n8n
ln -sf "$PERSISTENT/projects" /home/ubuntu/projects
ln -sf "$PERSISTENT/venv" /home/ubuntu/venv
log "Symlinks created"

# Install Ansible if needed
if ! command -v ansible-playbook &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq ansible
    log "Ansible installed"
fi

# Run Ansible
log "Starting Ansible playbook"
cd "$PERSISTENT/ansible"
ansible-playbook site.yml \
    -e "model=${MODEL:-deepseek-r1-70b}" \
    -e "lease_hours=${LEASE_HOURS:-4}" \
    -e "lambda_api_key=$LAMBDA_API_KEY" \
    -e "status_token=$STATUS_DAEMON_TOKEN" \
    -e "n8n_token=$N8N_TOKEN" \
    2>&1 | tee -a "$LOG"

log "GPU Stack boot complete"
