#!/bin/bash

# Docker Hub Build and Push Script for SeekrAI
# Usage: ./docker-build-push.sh [version]

set -e

# Configuration
DOCKER_USERNAME="lordherdier"
IMAGE_NAME="seekrai"
DEFAULT_VERSION="1.0.0"

# Get version from argument or use default
VERSION=${1:-$DEFAULT_VERSION}
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

echo "🐳 Building SeekrAI Docker Image"
echo "================================"
echo "Username: $DOCKER_USERNAME"
echo "Image: $IMAGE_NAME"
echo "Version: $VERSION"
echo "Build Date: $BUILD_DATE"
echo "================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build the image
echo "🔨 Building Docker image..."
docker build \
    --build-arg VERSION="$VERSION" \
    --build-arg BUILD_DATE="$BUILD_DATE" \
    -t "$DOCKER_USERNAME/$IMAGE_NAME:latest" \
    -t "$DOCKER_USERNAME/$IMAGE_NAME:v$VERSION" \
    .

echo "✅ Build completed successfully!"

# Ask user if they want to push
read -p "🚀 Do you want to push to Docker Hub? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📤 Pushing to Docker Hub..."
    
    # Check if logged in
    if ! docker info | grep -q "Username:"; then
        echo "🔐 Please login to Docker Hub first:"
        docker login
    fi
    
    # Push both tags
    echo "📤 Pushing latest tag..."
    docker push "$DOCKER_USERNAME/$IMAGE_NAME:latest"
    
    echo "📤 Pushing version tag..."
    docker push "$DOCKER_USERNAME/$IMAGE_NAME:v$VERSION"
    
    echo "✅ Successfully pushed to Docker Hub!"
    echo "🌐 Your image is available at: https://hub.docker.com/r/$DOCKER_USERNAME/$IMAGE_NAME"
else
    echo "⏭️  Skipping push to Docker Hub"
fi

# Show image info
echo ""
echo "📋 Image Information:"
echo "  Repository: $DOCKER_USERNAME/$IMAGE_NAME"
echo "  Tags: latest, v$VERSION"
echo "  Size: $(docker images "$DOCKER_USERNAME/$IMAGE_NAME:latest" --format "table {{.Size}}" | tail -n +2)"

# Show usage examples
echo ""
echo "🚀 Usage Examples:"
echo "  docker run -p 5000:5000 $DOCKER_USERNAME/$IMAGE_NAME:latest"
echo "  docker-compose up (using docker-compose.yml)"
echo ""
echo "✨ Done!" 