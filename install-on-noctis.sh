#!/bin/bash
# Run this script ON the noctis server after copying files
set -e

INSTALL_DIR="/home/quantic/NoctIS"
BREACHES_DIR="/home/quantic/NoctIS/breaches"

echo "🚀 Installing NoctIS on noctis server..."

# Extract files
echo "📦 Extracting files..."
mkdir -p ${INSTALL_DIR}
cd ${INSTALL_DIR}
tar -xzf /tmp/noctis-deploy.tar.gz
rm /tmp/noctis-deploy.tar.gz

# Create data directories
echo "📁 Creating data directories..."
mkdir -p ${BREACHES_DIR}
mkdir -p /home/quantic/NoctIS/data/typesense

# Create .env file if it doesn't exist
if [ ! -f ${INSTALL_DIR}/.env ]; then
    echo "🔑 Creating .env file..."
    cp ${INSTALL_DIR}/.env.example ${INSTALL_DIR}/.env
    echo "⚠️  IMPORTANT: Edit ${INSTALL_DIR}/.env and change TYPESENSE_API_KEY!"
fi

# Install Docker if needed
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    sudo usermod -aG docker $USER
    rm /tmp/get-docker.sh
    echo "✅ Docker installed! You may need to log out and back in for group changes to take effect."
    echo "   Or run: newgrp docker"
else
    echo "✅ Docker already installed"
fi

# Build and start containers
echo "🔨 Building containers..."
sudo docker compose -f docker-compose.prod.yml --env-file .env build

echo "🚀 Starting containers..."
sudo docker compose -f docker-compose.prod.yml --env-file .env up -d

# Show status
echo ""
echo "✨ Installation complete!"
echo ""
echo "📊 Container status:"
sudo docker compose -f docker-compose.prod.yml ps
echo ""
echo "🌐 Application running on http://noctis (port 80)"
echo ""
echo "📝 Useful commands:"
echo "  View logs: sudo docker compose -f docker-compose.prod.yml logs -f"
echo "  Stop:      sudo docker compose -f docker-compose.prod.yml down"
echo "  Restart:   sudo docker compose -f docker-compose.prod.yml restart"
