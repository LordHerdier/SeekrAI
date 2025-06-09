# SeekrAI Production Deployment Guide

This guide covers deploying SeekrAI in a production environment using Docker and Docker Compose.

## 🚀 Quick Start

1. **Clone and configure**:
   ```bash
   git clone https://github.com/LordHerdier/seekrai.git
   cd seekrai
   cp .env.production .env
   # Edit .env with your actual values
   ```

2. **Deploy**:
   ```bash
   ./deploy.sh
   ```

3. **Access**:
   - Application: http://localhost:5000
   - Health Check: http://localhost:5000/health

## 📋 Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended), macOS, or Windows with WSL2
- **CPU**: 2+ cores recommended
- **RAM**: 1GB minimum, 4GB recommended
- **Storage**: 10GB minimum free space
- **Network**: Internet access for API calls and job scraping

### Software Requirements
- Docker 20.10+ ([Installation Guide](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ ([Installation Guide](https://docs.docker.com/compose/install/))
- curl (for health checks)
- Optional: jq (for JSON formatting)

## ⚙️ Configuration

### Environment Variables

Copy `.env.production` to `.env` and update the following critical variables:

```bash
# REQUIRED - Update these values
SECRET_KEY=your_production_secret_key_here_make_it_long_and_random
OPENAI_API_KEY=your_openai_api_key_here

# OPTIONAL - Customize as needed
FLASK_ENV=production
PORT=5000
GUNICORN_WORKERS=4
LOG_LEVEL=INFO
```

### Generate SECRET_KEY

```bash
# Python method
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL method
openssl rand -base64 32
```

### Configuration Files

| File | Purpose | Required |
|------|---------|----------|
| `.env` | Environment variables | ✅ Yes |
| `config/config.yaml` | Application configuration | ✅ Yes |
| `gunicorn.conf.py` | Gunicorn server configuration | ✅ Yes |

## 🐳 Docker Deployment

### Basic Deployment

```bash
# Deploy with default settings
./deploy.sh

# Or manually
docker-compose up -d
```

### Custom Configuration

```bash
# Use custom environment file
docker-compose --env-file .env.staging up -d

# View configuration before deploying
docker-compose config
```

## 🔧 Deployment Script Usage

The `deploy.sh` script provides several commands:

```bash
# Deploy application
./deploy.sh deploy  # or just ./deploy.sh

# Stop all services
./deploy.sh stop

# Restart services
./deploy.sh restart

# View live logs
./deploy.sh logs

# Check service status
./deploy.sh status

# Check application health
./deploy.sh health
```

## 🏥 Health Checks

SeekrAI includes comprehensive health monitoring:

### Endpoints

- **Basic Health**: `GET /health`
- **Detailed Health**: `GET /health/detailed`  
- **Readiness**: `GET /ready`

### Example Health Check

```bash
# Basic health check
curl http://localhost:5000/health

# Detailed health check with system info
curl http://localhost:5000/health/detailed | jq .
```

### Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00.000000",
  "version": "1.0.0",
  "uptime": 3600.5
}
```

## 📊 Monitoring and Logging

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f seekrai

# With timestamps
docker-compose logs -f -t seekrai
```

### Log Locations

- **Application Logs**: `logs/` directory (mounted volume)
- **Redis Logs**: Container logs only

### Monitoring Integration

The application is ready for monitoring integration:

- Prometheus metrics endpoint (future feature)
- Health check endpoints for load balancers
- Structured JSON logging for log aggregation

## 🔒 Security Considerations

### Production Security Checklist

- [ ] Update `SECRET_KEY` to a secure random value
- [ ] Use HTTPS in production (add your own reverse proxy/load balancer)
- [ ] Implement proper firewall rules
- [ ] Regular security updates for base images
- [ ] Monitor logs for suspicious activity
- [ ] Use secrets management for sensitive data

### Reverse Proxy Setup

For production, you should set up your own reverse proxy (nginx, Traefik, Caddy, etc.) to handle:

- **SSL/HTTPS termination**
- **Rate limiting**
- **Load balancing** (if running multiple instances)
- **Static file serving**
- **Security headers**

Example nginx upstream configuration:
```nginx
upstream seekrai_backend {
    server localhost:5000;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://seekrai_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🚨 Troubleshooting

### Common Issues

#### Application Won't Start

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs seekrai

# Check configuration
docker-compose config
```

#### Health Check Failing

```bash
# Check application logs
docker-compose logs -f seekrai

# Test health endpoint directly
curl -v http://localhost:5000/health

# Check if all required directories exist
docker-compose exec seekrai ls -la /app/
```

#### Out of Memory

```bash
# Check container resource usage
docker stats

# Reduce Gunicorn workers
# In .env: GUNICORN_WORKERS=2
```

#### File Upload Issues

```bash
# Check upload directory permissions
docker-compose exec seekrai ls -la /app/uploads/

# Check disk space
docker-compose exec seekrai df -h
```

### Performance Tuning

#### Optimize for High Load

```bash
# Increase workers
export GUNICORN_WORKERS=8

# Use Redis for caching
export REDIS_URL=redis://redis:6379/0
```

#### Memory Optimization

```bash
# Reduce batch sizes in config.yaml
job_analysis:
  batch_size: 3
  max_parallel_batches: 2

# Cleanup old files regularly
cleanup:
  auto_cleanup_on_startup: true
  default_days_old: 7
```

## 🔄 Updates and Maintenance

### Application Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and redeploy
./deploy.sh

# Or manually
docker-compose build --no-cache
docker-compose up -d
```

### Database Backups

```bash
# Backup Redis data
docker-compose exec redis redis-cli BGSAVE

# Copy backup file
docker cp seekrai-redis:/data/dump.rdb ./backups/
```

### Log Rotation

Configure log rotation to prevent disk space issues:

```bash
# Example logrotate configuration
/path/to/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 seekrai seekrai
    postrotate
        docker-compose restart seekrai
    endscript
}
```

## 🌐 Production Deployment Architectures

### Single Server Deployment

```
Internet → [Your Reverse Proxy] → [SeekrAI Container] → [Redis Container]
```

### Load Balanced Deployment

```
Internet → [Load Balancer] → [Your Reverse Proxy] → [SeekrAI Instances] → [Redis Cluster]
```

### Cloud Deployment Options

- **AWS**: ECS/Fargate with RDS Redis
- **Google Cloud**: Cloud Run with MemoryStore Redis  
- **Azure**: Container Instances with Azure Cache for Redis
- **DigitalOcean**: App Platform or Droplets with managed Redis

## 📞 Support

### Getting Help

1. Check this documentation
2. Review application logs
3. Check GitHub issues
4. Contact the development team

### Useful Commands Reference

```bash
# Quick deployment
./deploy.sh

# View all logs
docker-compose logs -f

# Health check
curl http://localhost:5000/health

# Stop everything
docker-compose down

# Clean rebuild
docker-compose down && docker-compose build --no-cache && docker-compose up -d

# Shell access
docker-compose exec seekrai bash

# Database shell (Redis)
docker-compose exec redis redis-cli
```

## 📝 Change Log

- **v1.0.0**: Initial production deployment setup
  - Docker containerization
  - Health checks
  - Redis caching
  - Production configuration

---

For development setup, see the main README.md file. 