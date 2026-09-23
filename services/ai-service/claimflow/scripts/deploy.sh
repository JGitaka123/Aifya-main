#!/bin/bash

# Configuration
VERSION=${VERSION:-"latest"}
REGISTRY=${DOCKER_REGISTRY:-"your-registry-here"}

echo "🚢 Deploying Claimflow (Version: $VERSION, Registry: $REGISTRY)..."

# Ensure we are in the root directory
cd "$(dirname "$0")/.."

# Export variables for docker-compose
export DOCKER_REGISTRY=$REGISTRY
export VERSION=$VERSION

# Pull latest images
echo "📥 Pulling latest images..."
docker compose -f docker/docker-compose.prod.yml pull

# Restart the stack
echo "♻️ Restarting stack..."
docker compose -f docker/docker-compose.prod.yml up -d --remove-orphans

# Monitoring
echo "📈 Current status:"
docker compose -f docker/docker-compose.prod.yml ps

echo "✅ Deployment complete!"
