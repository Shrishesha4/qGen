#!/bin/bash

# Build and Push Script for Question Bank Generator
# This script builds multi-architecture Docker images and pushes them to DockerHub

set -e  # Exit on error

# Configuration
DOCKER_USERNAME="shrishesha4"
REPO_NAME="qgen"
IMAGE_NAME="${DOCKER_USERNAME}/${REPO_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get version from argument or default to 'latest'
VERSION="${1:-latest}"

print_info "Starting multi-architecture build process for ${IMAGE_NAME}:${VERSION}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    print_warn "docker buildx not found. Installing buildx..."
    docker buildx create --name multiarch --use || true
    docker buildx use multiarch
fi

# Build the frontend first (to copy dist folder)
print_info "Building frontend..."
cd app
npm install
npm run build
cd ..

# Copy built frontend to a temporary location for nginx
print_info "Preparing frontend files for deployment..."
rm -rf frontend-dist
cp -r app/dist frontend-dist

# Login to DockerHub
print_info "Logging in to DockerHub..."
if ! docker login; then
    print_error "Failed to login to DockerHub"
    exit 1
fi

# Build and push for multiple architectures
print_info "Building and pushing Docker image for linux/amd64,linux/arm64..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t ${IMAGE_NAME}:${VERSION} \
    $([ "$VERSION" != "latest" ] && echo "-t ${IMAGE_NAME}:latest" || echo "") \
    --push \
    .

print_info "Build and push completed successfully!"
print_info "Image: ${IMAGE_NAME}:${VERSION}"
print_info "Platforms: linux/amd64, linux/arm64"

# Display summary
echo ""
print_info "Summary:"
echo "  - Image: ${IMAGE_NAME}:${VERSION}"
if [ "$VERSION" != "latest" ]; then
    echo "  - Also tagged as: ${IMAGE_NAME}:latest"
fi
echo "  - Architectures: amd64, arm64"
echo "  - Frontend build: $(ls -lh frontend-dist/index.html | awk '{print $5}')"
echo ""
print_info "To pull and run:"
echo "  docker pull ${IMAGE_NAME}:${VERSION}"
echo "  docker run -p 8000:8000 -e GEMINI_API_KEY=your_key ${IMAGE_NAME}:${VERSION}"
echo ""
print_info "For production deployment, use docker-compose.prod.yml"
