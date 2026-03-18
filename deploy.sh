#!/bin/bash
set -e

# NoctIS Deployment Script for noctis server
# This script deploys the NoctIS OSINT toolbox to the remote server

# Configuration
REMOTE_USER="quantic"
REMOTE_HOST="noctis"
REMOTE_DIR="/home/quantic/NoctIS"
OSINT_DATA_DIR="/home/quantic/NoctIS/breaches"

echo "🚀 Starting NoctIS deployment to ${REMOTE_HOST}..."

# Check SSH connectivity
echo "📡 Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 ${REMOTE_USER}@${REMOTE_HOST} "echo 'SSH connection successful'"; then
    echo "❌ Failed to connect to ${REMOTE_HOST}. Please check your SSH configuration."
    exit 1
fi

# Install Docker if not present
echo "🐳 Checking Docker installation..."
ssh ${REMOTE_USER}@${REMOTE_HOST} bash << 'ENDSSH'
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add user to docker group
    sudo usermod -aG docker $USER
    echo "✅ Docker installed successfully"
else
    echo "✅ Docker already installed"
fi
ENDSSH

# Create remote directory structure
echo "📁 Creating directory structure on ${REMOTE_HOST}..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_DIR} ${OSINT_DATA_DIR}"

# Sync project files to remote server
echo "📤 Syncing project files..."
rsync -avz --exclude 'node_modules' --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
    ./ ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/

# Build and start containers
echo "🔨 Building and starting containers on ${REMOTE_HOST}..."
ssh ${REMOTE_USER}@${REMOTE_HOST} bash << ENDSSH
cd ${REMOTE_DIR}
sudo docker compose -f docker-compose.prod.yml down 2>/dev/null || true
sudo docker compose -f docker-compose.prod.yml build
sudo docker compose -f docker-compose.prod.yml up -d
echo "✅ Containers started successfully"
ENDSSH

# Show status
echo ""
echo "✨ Deployment complete!"
echo ""
echo "📊 Container status:"
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_DIR} && sudo docker compose -f docker-compose.prod.yml ps"
echo ""
echo "🌐 Access the application at: http://${REMOTE_HOST}"
echo ""
echo "📝 Useful commands:"
echo "  View logs: ssh ${REMOTE_USER}@${REMOTE_HOST} 'cd ${REMOTE_DIR} && sudo docker compose -f docker-compose.prod.yml logs -f'"
echo "  Stop app:  ssh ${REMOTE_USER}@${REMOTE_HOST} 'cd ${REMOTE_DIR} && sudo docker compose -f docker-compose.prod.yml down'"
echo "  Restart:   ssh ${REMOTE_USER}@${REMOTE_HOST} 'cd ${REMOTE_DIR} && sudo docker compose -f docker-compose.prod.yml restart'"
