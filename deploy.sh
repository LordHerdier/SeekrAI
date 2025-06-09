#!/bin/bash

# SeekrAI Production Deployment Script
# This script helps deploy SeekrAI in production with Docker Compose

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="SeekrAI"
DOCKER_COMPOSE_FILE="docker-compose.yml"
DEV_DOCKER_COMPOSE_FILE="docker-compose.dev.yml"
ENV_FILE=".env"
PRODUCTION_ENV_TEMPLATE=".env.production"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking deployment requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_warning ".env file not found. Creating from template..."
        if [ -f "$PRODUCTION_ENV_TEMPLATE" ]; then
            cp "$PRODUCTION_ENV_TEMPLATE" "$ENV_FILE"
            log_warning "Please edit .env file and update the required values before running again."
            exit 1
        else
            log_error "Neither .env nor .env.production template found."
            exit 1
        fi
    fi
    
    log_success "All requirements satisfied."
}

validate_env() {
    log_info "Validating environment configuration..."
    
    # Source the .env file
    set -o allexport
    source "$ENV_FILE"
    set +o allexport
    
    # Check critical environment variables
    REQUIRED_VARS=("SECRET_KEY" "OPENAI_API_KEY")
    MISSING_VARS=()
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ] || [ "${!var}" == "your_"* ]; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -ne 0 ]; then
        log_error "Missing or invalid required environment variables:"
        printf '%s\n' "${MISSING_VARS[@]}"
        log_error "Please update your .env file with valid values."
        exit 1
    fi
    
    log_success "Environment configuration is valid."
}

build_and_deploy() {
    log_info "Deploying $APP_NAME..."
    
    # Determine which compose file to use
    local compose_file="$DOCKER_COMPOSE_FILE"
    local mode="production"
    
    # Check if we're in development mode
    if [ "${1:-}" == "dev" ] || [ "${FLASK_ENV:-}" == "development" ]; then
        compose_file="$DEV_DOCKER_COMPOSE_FILE"
        mode="development"
        log_info "Using development mode (local build)"
    else
        log_info "Using production mode (Docker Hub image)"
    fi
    
    # Set build date
    export BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
    
    # Build and start services
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose -f $compose_file"
    else
        COMPOSE_CMD="docker compose -f $compose_file"
    fi
    
    if [ "$mode" == "development" ]; then
        log_info "Building Docker images locally..."
        $COMPOSE_CMD build --no-cache
    else
        log_info "Pulling Docker images from Docker Hub..."
        $COMPOSE_CMD pull
    fi
    
    log_info "Starting services..."
    $COMPOSE_CMD up -d
    
    log_success "Services started successfully in $mode mode."
}

wait_for_health() {
    log_info "Waiting for application to become healthy..."
    
    MAX_ATTEMPTS=30
    ATTEMPT=1
    
    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
        if curl -f -s http://localhost:${PORT:-5000}/health > /dev/null 2>&1; then
            log_success "Application is healthy!"
            return 0
        fi
        
        log_info "Attempt $ATTEMPT/$MAX_ATTEMPTS - Application not ready yet..."
        sleep 10
        ((ATTEMPT++))
    done
    
    log_error "Application failed to become healthy within expected time."
    log_info "Checking container logs..."
    $COMPOSE_CMD logs --tail=50 seekrai
    return 1
}

show_status() {
    log_info "Deployment Status:"
    echo
    
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    
    $COMPOSE_CMD ps
    echo
    
    log_info "Application URLs:"
    echo "  - Main Application: http://localhost:${PORT:-5000}"
    echo "  - Health Check: http://localhost:${PORT:-5000}/health"
    echo "  - Detailed Health: http://localhost:${PORT:-5000}/health/detailed"
}

cleanup_old_containers() {
    log_info "Cleaning up old containers and images..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove dangling images
    docker image prune -f
    
    log_success "Cleanup completed."
}

# Main deployment process
main() {
    echo "============================================"
    echo "  $APP_NAME Production Deployment Script"
    echo "============================================"
    echo
    
    check_requirements
    validate_env
    
    # Ask for confirmation in production
    if [ "${FLASK_ENV:-}" == "production" ]; then
        read -p "Are you sure you want to deploy to PRODUCTION? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled."
            exit 0
        fi
    fi
    
    cleanup_old_containers
    build_and_deploy "$1"
    
    if wait_for_health; then
        show_status
        log_success "$APP_NAME deployed successfully!"
        echo
        log_info "Useful commands:"
        echo "  - View logs: docker-compose logs -f"
        echo "  - Stop services: docker-compose down"
        echo "  - Restart: docker-compose restart"
        echo "  - Update: git pull && ./deploy.sh"
    else
        log_error "Deployment completed but application is not healthy."
        exit 1
    fi
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy"|"dev")
        main "$1"
        ;;
    "stop")
        log_info "Stopping $APP_NAME services..."
        # Try to stop both production and dev versions
        for compose_file in "$DOCKER_COMPOSE_FILE" "$DEV_DOCKER_COMPOSE_FILE"; do
            if [ -f "$compose_file" ]; then
                if command -v docker-compose &> /dev/null; then
                    docker-compose -f "$compose_file" down 2>/dev/null || true
                else
                    docker compose -f "$compose_file" down 2>/dev/null || true
                fi
            fi
        done
        log_success "Services stopped."
        ;;
    "restart")
        log_info "Restarting $APP_NAME services..."
        # Determine which compose file is running
        local active_compose="$DOCKER_COMPOSE_FILE"
        if docker ps --format "table {{.Names}}" | grep -q "seekrai-app-dev"; then
            active_compose="$DEV_DOCKER_COMPOSE_FILE"
        fi
        
        if command -v docker-compose &> /dev/null; then
            docker-compose -f "$active_compose" restart
        else
            docker compose -f "$active_compose" restart
        fi
        log_success "Services restarted."
        ;;
    "logs")
        # Determine which compose file is running
        local active_compose="$DOCKER_COMPOSE_FILE"
        if docker ps --format "table {{.Names}}" | grep -q "seekrai-app-dev"; then
            active_compose="$DEV_DOCKER_COMPOSE_FILE"
        fi
        
        if command -v docker-compose &> /dev/null; then
            docker-compose -f "$active_compose" logs -f
        else
            docker compose -f "$active_compose" logs -f
        fi
        ;;
    "status")
        show_status
        ;;
    "health")
        curl -s http://localhost:${PORT:-5000}/health | jq . || curl -s http://localhost:${PORT:-5000}/health
        ;;
    *)
        echo "Usage: $0 [deploy|dev|stop|restart|logs|status|health]"
        echo
        echo "Commands:"
        echo "  deploy  - Deploy using Docker Hub image (production)"
        echo "  dev     - Deploy using local build (development)"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - Show live logs"
        echo "  status  - Show service status"
        echo "  health  - Check application health"
        echo
        echo "Examples:"
        echo "  ./deploy.sh         # Production deployment (Docker Hub)"
        echo "  ./deploy.sh dev     # Development deployment (local build)"
        echo "  ./deploy.sh stop    # Stop all services"
        exit 1
        ;;
esac 