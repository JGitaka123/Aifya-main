#!/bin/bash

# Configuration
REGISTRY=${DOCKER_REGISTRY:-"your-registry-here"}
VERSION=${VERSION:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}

echo "🚀 Building Claimflow images (Version: $VERSION, Registry: $REGISTRY)..."

log() {
  printf "[build] %s\n" "$*"
}

# Ensure we are in the root directory
cd "$(dirname "$0")/.."

# Export variables for docker-compose
export DOCKER_REGISTRY=$REGISTRY
export VERSION=$VERSION

# Load environment from packages/web/.env if available
if [ -f "packages/web/.env" ]; then
  log "Loading environment from packages/web/.env"
  # Use a subshell to avoid polluting the current shell, but we need the exports
  set -a
  source packages/web/.env
  set +a
fi

# Map variables to what docker-compose.prod.yml expects
export PUBLIC_API_URL="${NEXT_PUBLIC_API_BASE_URL:-}"
export FIREBASE_API_KEY="${NEXT_PUBLIC_FIREBASE_API_KEY:-}"
export FIREBASE_AUTH_DOMAIN="${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN:-}"
export FIREBASE_PROJECT_ID="${NEXT_PUBLIC_FIREBASE_PROJECT_ID:-}"
export FIREBASE_STORAGE_BUCKET="${NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET:-}"
export FIREBASE_MESSAGING_SENDER_ID="${NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID:-}"
export FIREBASE_APP_ID="${NEXT_PUBLIC_FIREBASE_APP_ID:-}"
export FIREBASE_MEASUREMENT_ID="${NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID:-}"

# Check for mandatory variables
if [ -z "$PUBLIC_API_URL" ]; then
  echo "⚠️  Warning: PUBLIC_API_URL (NEXT_PUBLIC_API_BASE_URL) is not set."
fi

# Build images
docker compose -f docker/docker-compose.prod.yml build

# Push images
echo "📤 Pushing images to $REGISTRY..."
docker push "$REGISTRY/api:$VERSION"
docker push "$REGISTRY/web:$VERSION"
docker push "$REGISTRY/ml:$VERSION"

echo "✅ Build and push complete!"
