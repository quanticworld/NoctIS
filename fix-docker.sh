#!/bin/bash
# Docker diagnostic and fix script

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Docker Diagnostic & Fix Script${NC}"
echo ""

# Function to run commands with sudo prompt
run_sudo() {
    echo -e "${YELLOW}Running: $@${NC}"
    sudo "$@"
}

echo -e "${BLUE}Step 1: Checking Docker status${NC}"
systemctl status docker --no-pager || true
echo ""

echo -e "${BLUE}Step 2: Checking containerd${NC}"
if systemctl is-active --quiet containerd; then
    echo -e "${GREEN}✓ containerd is running${NC}"
else
    echo -e "${YELLOW}⚠ containerd is not running, starting it...${NC}"
    run_sudo systemctl start containerd
    sleep 2
fi
echo ""

echo -e "${BLUE}Step 3: Checking Docker socket${NC}"
if [ -S /var/run/docker.sock ]; then
    echo -e "${GREEN}✓ Docker socket exists${NC}"
    ls -la /var/run/docker.sock
else
    echo -e "${RED}✗ Docker socket missing${NC}"
fi
echo ""

echo -e "${BLUE}Step 4: Checking iptables${NC}"
run_sudo iptables -L -n | head -10 || echo -e "${YELLOW}⚠ iptables check failed${NC}"
echo ""

echo -e "${BLUE}Step 5: Cleaning Docker state${NC}"
echo "Stopping Docker..."
run_sudo systemctl stop docker.socket 2>/dev/null || true
run_sudo systemctl stop docker.service 2>/dev/null || true
sleep 2

echo "Removing Docker socket..."
run_sudo rm -f /var/run/docker.sock
run_sudo rm -f /var/run/docker.pid
echo ""

echo -e "${BLUE}Step 6: Checking disk space${NC}"
df -h / | grep -v Filesystem
echo ""

echo -e "${BLUE}Step 7: Starting containerd${NC}"
run_sudo systemctl restart containerd
sleep 2
if systemctl is-active --quiet containerd; then
    echo -e "${GREEN}✓ containerd started successfully${NC}"
else
    echo -e "${RED}✗ containerd failed to start${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}Step 8: Starting Docker${NC}"
run_sudo systemctl start docker
sleep 3
echo ""

echo -e "${BLUE}Step 9: Checking Docker status${NC}"
if systemctl is-active --quiet docker; then
    echo -e "${GREEN}✅ Docker is running!${NC}"
    echo ""
    docker --version
    echo ""
    echo -e "${GREEN}Testing Docker:${NC}"
    docker ps
    echo ""
    echo -e "${GREEN}✅ Docker is working correctly!${NC}"
else
    echo -e "${RED}✗ Docker failed to start${NC}"
    echo ""
    echo -e "${YELLOW}Checking logs:${NC}"
    run_sudo journalctl -xeu docker.service --no-pager -n 30
    exit 1
fi
