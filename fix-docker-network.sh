#!/bin/bash
# Fix Docker network issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing Docker Network Issues${NC}"
echo ""

# Function to run commands with sudo
run_sudo() {
    echo -e "${YELLOW}Running: $@${NC}"
    sudo "$@"
}

echo -e "${BLUE}Step 1: Stop Docker completely${NC}"
run_sudo systemctl stop docker.socket 2>/dev/null || true
run_sudo systemctl stop docker.service 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Docker stopped${NC}"
echo ""

echo -e "${BLUE}Step 2: Remove Docker network interfaces${NC}"
# Remove all Docker bridge interfaces
for iface in $(ip link show | grep -o 'br-[a-z0-9]*' || true); do
    echo -e "${YELLOW}Removing interface: $iface${NC}"
    run_sudo ip link set $iface down 2>/dev/null || true
    run_sudo ip link delete $iface 2>/dev/null || true
done

# Remove docker0
if ip link show docker0 >/dev/null 2>&1; then
    echo -e "${YELLOW}Removing docker0 interface${NC}"
    run_sudo ip link set docker0 down 2>/dev/null || true
    run_sudo ip link delete docker0 2>/dev/null || true
fi
echo -e "${GREEN}✓ Network interfaces cleaned${NC}"
echo ""

echo -e "${BLUE}Step 3: Clean Docker network state${NC}"
run_sudo rm -rf /var/lib/docker/network 2>/dev/null || true
run_sudo mkdir -p /var/lib/docker/network
echo -e "${GREEN}✓ Network state cleaned${NC}"
echo ""

echo -e "${BLUE}Step 4: Clean iptables rules${NC}"
echo -e "${YELLOW}Flushing Docker iptables rules...${NC}"
run_sudo iptables -t nat -F DOCKER 2>/dev/null || true
run_sudo iptables -t filter -F DOCKER 2>/dev/null || true
run_sudo iptables -t filter -F DOCKER-ISOLATION-STAGE-1 2>/dev/null || true
run_sudo iptables -t filter -F DOCKER-ISOLATION-STAGE-2 2>/dev/null || true
run_sudo iptables -t nat -X DOCKER 2>/dev/null || true
run_sudo iptables -t filter -X DOCKER 2>/dev/null || true
run_sudo iptables -t filter -X DOCKER-ISOLATION-STAGE-1 2>/dev/null || true
run_sudo iptables -t filter -X DOCKER-ISOLATION-STAGE-2 2>/dev/null || true
echo -e "${GREEN}✓ iptables cleaned${NC}"
echo ""

echo -e "${BLUE}Step 5: Remove Docker runtime state${NC}"
run_sudo rm -f /var/run/docker.sock
run_sudo rm -f /var/run/docker.pid
echo -e "${GREEN}✓ Runtime state cleaned${NC}"
echo ""

echo -e "${BLUE}Step 6: Restart containerd${NC}"
run_sudo systemctl restart containerd
sleep 2
if systemctl is-active --quiet containerd; then
    echo -e "${GREEN}✓ containerd running${NC}"
else
    echo -e "${RED}✗ containerd failed${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}Step 7: Start Docker${NC}"
run_sudo systemctl start docker
sleep 3
echo ""

echo -e "${BLUE}Step 8: Verify Docker${NC}"
if systemctl is-active --quiet docker; then
    echo -e "${GREEN}✅ Docker is running!${NC}"
    echo ""
    docker --version
    echo ""
    echo -e "${GREEN}Testing Docker network:${NC}"
    docker network ls
    echo ""
    echo -e "${GREEN}✅ Docker network is working!${NC}"
    echo ""
    echo -e "${GREEN}You can now run: docker-compose up -d${NC}"
else
    echo -e "${RED}✗ Docker still failing${NC}"
    echo ""
    echo -e "${YELLOW}Latest logs:${NC}"
    run_sudo journalctl -xeu docker.service --no-pager -n 20
    exit 1
fi
