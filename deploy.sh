#!/bin/bash

# Quick Deploy Script for Question Bank Generator
# This script helps deploy the application to a server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    print_info "Creating .env from .env.example..."
    cp .env.example .env
    print_warn "Please edit .env file with your configuration before proceeding."
    print_warn "Especially set GEMINI_API_KEY and SECRET_KEY"
    exit 1
fi

# Check if GEMINI_API_KEY is set
source .env
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    print_error "GEMINI_API_KEY not set in .env file!"
    exit 1
fi

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "your_secret_key_here" ]; then
    print_error "SECRET_KEY not set in .env file!"
    print_info "Generate one with: openssl rand -hex 32"
    exit 1
fi

print_step "Starting deployment..."

# Check if frontend-dist exists
if [ ! -d "frontend-dist" ]; then
    print_warn "frontend-dist directory not found. Building frontend..."
    
    if [ ! -d "app" ]; then
        print_error "app directory not found!"
        exit 1
    fi
    
    cd app
    print_info "Installing frontend dependencies..."
    npm install
    
    print_info "Building frontend..."
    npm run build
    
    cd ..
    print_info "Copying built frontend..."
    cp -r app/dist frontend-dist
fi

# Pull latest image
print_step "Pulling latest Docker image..."
docker pull shrishesha4/qgen:latest

# Stop existing containers
print_step "Stopping existing containers (if any)..."
docker-compose -f docker-compose.prod.yml down || true

# Start services
print_step "Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
print_step "Waiting for services to start..."
sleep 5

# Check service status
print_step "Checking service status..."
docker-compose -f docker-compose.prod.yml ps

# Test health endpoint
print_step "Testing health endpoint..."
if curl -f http://localhost/api/health > /dev/null 2>&1; then
    print_info "✓ Health check passed!"
else
    print_warn "Health check failed. Check logs with: docker-compose -f docker-compose.prod.yml logs"
fi

print_info ""
print_info "======================================"
print_info "Deployment completed successfully!"
print_info "======================================"
print_info ""
print_info "Application is running at:"
print_info "  - HTTP: http://localhost"
print_info "  - API Docs: http://localhost/docs"
print_info ""
print_info "Useful commands:"
print_info "  View logs: docker-compose -f docker-compose.prod.yml logs -f"
print_info "  Stop services: docker-compose -f docker-compose.prod.yml down"
print_info "  Restart: docker-compose -f docker-compose.prod.yml restart"
print_info ""
