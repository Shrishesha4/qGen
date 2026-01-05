#!/bin/bash
# Quick Start Script for Question Bank Generator

set -e

echo "🚀 Question Bank Generator - Docker Quick Start"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your GEMINI_API_KEY"
    echo ""
    read -p "Press Enter after you've updated the .env file..."
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Error: docker-compose not found. Please install Docker Compose."
    exit 1
fi

echo "🏗️  Building Docker image..."
$COMPOSE_CMD build

echo ""
echo "🚀 Starting application..."
$COMPOSE_CMD up -d

echo ""
echo "✅ Application started successfully!"
echo ""
echo "📊 Access the application at: http://localhost:8000"
echo ""
echo "👤 Default admin credentials:"
echo "   Email: admin@example.com"
echo "   Password: admin"
echo ""
echo "⚠️  Remember to change the admin password after first login!"
echo ""
echo "📝 Useful commands:"
echo "   View logs:    $COMPOSE_CMD logs -f"
echo "   Stop:         $COMPOSE_CMD down"
echo "   Restart:      $COMPOSE_CMD restart"
echo ""
