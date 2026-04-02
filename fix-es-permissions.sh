#!/bin/bash
# Fix Elasticsearch permissions on remote server

echo "Stopping Elasticsearch container..."
cd /home/quantic/NoctIS
docker compose -f docker-compose.prod.yml stop elasticsearch

echo "Removing old data directory..."
sudo rm -rf /home/quantic/NoctIS/data/elasticsearch

echo "Creating new data directory with correct permissions..."
sudo mkdir -p /home/quantic/NoctIS/data/elasticsearch
sudo chown -R 1000:1000 /home/quantic/NoctIS/data/elasticsearch
sudo chmod -R 755 /home/quantic/NoctIS/data/elasticsearch

echo "Starting Elasticsearch container..."
docker compose -f docker-compose.prod.yml up -d elasticsearch

echo "Done! Waiting for Elasticsearch to start..."
sleep 10
docker logs noctis-elasticsearch-1 --tail 20
