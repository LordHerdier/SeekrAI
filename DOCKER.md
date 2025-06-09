# Docker Deployment Guide

## 🐳 Docker Hub Image

**Repository**: `lordherdier/seekrai`  
**URL**: https://hub.docker.com/r/lordherdier/seekrai

## 📦 Building and Pushing to Docker Hub

### Automated Build Script
```bash
# Build and push with default version
./docker-build-push.sh

# Build and push with specific version
./docker-build-push.sh 1.0.1
```

### Manual Commands
```bash
# Build image
docker build -t lordherdier/seekrai:latest -t lordherdier/seekrai:v1.0.0 .

# Push to Docker Hub
docker push lordherdier/seekrai:latest
docker push lordherdier/seekrai:v1.0.0
```

## 🚀 Deployment Options

### Option 1: Production Deployment (Docker Hub)
Uses pre-built images from Docker Hub. Faster deployment, smaller download.

```bash
# Quick start
./deploy.sh

# Manual
docker-compose up -d
```

**Features:**
- ✅ Uses Docker Hub image
- ✅ Fast deployment
- ✅ Production optimized
- ✅ No local build required

### Option 2: Development Deployment (Local Build)
Builds image locally with source code mounting for development.

```bash
# Quick start
./deploy.sh dev

# Manual
docker-compose -f docker-compose.dev.yml up -d
```

**Features:**
- ✅ Local source code mounting
- ✅ Development environment variables
- ✅ Debug logging enabled
- ✅ Rebuilds with code changes

## 📋 Environment Configuration

### Production (.env)
```env
# Required
SECRET_KEY=your_production_secret_key
OPENAI_API_KEY=your_openai_api_key

# Docker Hub Image
SEEKRAI_VERSION=latest

# Server
PORT=5000
GUNICORN_WORKERS=4
LOG_LEVEL=INFO
```

### Development
```env
# Same as production but with:
FLASK_ENV=development
LOG_LEVEL=DEBUG
GUNICORN_WORKERS=2
```

## 🛠️ Available Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh` | Production deployment (Docker Hub) |
| `./deploy.sh dev` | Development deployment (local build) |
| `./deploy.sh stop` | Stop all services |
| `./deploy.sh restart` | Restart services |
| `./deploy.sh logs` | View live logs |
| `./deploy.sh status` | Show service status |
| `./deploy.sh health` | Check application health |

## 🔧 Docker Compose Files

### docker-compose.yml (Production)
- Uses `lordherdier/seekrai:${SEEKRAI_VERSION:-latest}`
- Production environment settings
- Optimized for performance

### docker-compose.dev.yml (Development)  
- Builds locally with Dockerfile
- Mounts source code for live editing
- Development environment settings
- Debug logging enabled

## 📊 Version Management

### Tagging Strategy
- `latest` - Latest stable release
- `v1.0.0` - Specific version tags
- Custom tags supported via `SEEKRAI_VERSION` env var

### Example Version Deployment
```bash
# Use specific version
export SEEKRAI_VERSION=v1.0.0
./deploy.sh

# Or in .env file
echo "SEEKRAI_VERSION=v1.0.0" >> .env
./deploy.sh
```

## 🔍 Troubleshooting

### Check Running Containers
```bash
docker ps
# or
./deploy.sh status
```

### View Logs
```bash
./deploy.sh logs
# or
docker-compose logs -f seekrai
```

### Pull Latest Image
```bash
docker pull lordherdier/seekrai:latest
docker-compose up -d
```

### Force Rebuild (Development)
```bash
docker-compose -f docker-compose.dev.yml build --no-cache
docker-compose -f docker-compose.dev.yml up -d
```

## 🚀 Quick Reference

```bash
# First time setup
git clone https://github.com/LordHerdier/seekrai.git
cd seekrai
cp .env.production .env
# Edit .env file

# Production deployment
./deploy.sh

# Development deployment
./deploy.sh dev

# View application
open http://localhost:5000
``` 