#!/bin/bash
set -e

# Remove all containers, images, volumes, and cache for a fresh build
cd "$(dirname "$0")/.."

echo "Stopping and removing containers, images, volumes, and cache..."
COMPOSE_FILE="compose.yaml"
docker compose -f "$COMPOSE_FILE" down --rmi all --volumes --remove-orphans || true

echo "Pruning unused Docker data..."
docker system prune -af || true

echo "Building fresh image with no cache..."
docker compose -f "$COMPOSE_FILE" build --no-cache

echo "Starting up in detached mode..."
docker compose -f "$COMPOSE_FILE" up -d

echo "Done!"
