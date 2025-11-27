#!/bin/bash

# Creativity Engine Startup Script

set -e

echo "Starting Creativity Engine..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and add your API keys:"
    echo "   - OPENROUTER_API_KEY"
    echo "   - PINECONE_API_KEY"
    echo "   - PINECONE_ENVIRONMENT"
    echo ""
    read -p "Press Enter after you've updated .env with your credentials..."
fi

# Check for required API keys
if ! grep -q "your_openrouter_api_key_here" .env 2>/dev/null; then
    if ! grep -q "^OPENROUTER_API_KEY=sk-" .env 2>/dev/null; then
        echo "⚠️  Warning: OPENROUTER_API_KEY may not be set correctly in .env"
    fi
fi

echo "Building Docker images..."
docker-compose build

echo "Starting services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services started successfully!"
    echo ""
    echo "🚀 Creativity Engine is running!"
    echo ""
    echo "📚 Access points:"
    echo "   - API:          http://localhost:8000"
    echo "   - API Docs:     http://localhost:8000/docs"
    echo "   - Health Check: http://localhost:8000/health"
    echo "   - RabbitMQ:     http://localhost:15672 (user: creativity, pass: creativity_password_change_me)"
    echo ""
    echo "📊 View logs:"
    echo "   docker-compose logs -f api"
    echo "   docker-compose logs -f worker"
    echo ""
    echo "🛑 Stop services:"
    echo "   docker-compose down"
    echo ""
else
    echo "❌ Error: Services failed to start"
    echo "Check logs with: docker-compose logs"
    exit 1
fi
