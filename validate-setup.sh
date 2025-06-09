#!/bin/bash

# SeekrAI Production Setup Validation Script
# This script validates that all required files and configurations are present

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((CHECKS_PASSED++))
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    ((WARNINGS++))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((CHECKS_FAILED++))
}

check_file_exists() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        log_success "$description exists: $file"
        return 0
    else
        log_error "$description missing: $file"
        return 1
    fi
}

check_directory_exists() {
    local dir="$1"
    local description="$2"
    
    if [ -d "$dir" ]; then
        log_success "$description exists: $dir"
        return 0
    else
        log_error "$description missing: $dir"
        return 1
    fi
}

check_executable() {
    local cmd="$1"
    local description="$2"
    
    if command -v "$cmd" &> /dev/null; then
        local version=$(command -v "$cmd" && $cmd --version 2>&1 | head -n 1 || echo "Unknown version")
        log_success "$description is installed: $version"
        return 0
    else
        log_error "$description is not installed"
        return 1
    fi
}

validate_env_file() {
    log_info "Validating .env file..."
    
    if [ ! -f ".env" ]; then
        log_error ".env file not found"
        return 1
    fi
    
    # Source the .env file
    set -o allexport
    source .env 2>/dev/null || {
        log_error ".env file contains syntax errors"
        return 1
    }
    set +o allexport
    
    # Check critical variables
    local required_vars=("SECRET_KEY" "OPENAI_API_KEY")
    local all_present=0  # 0 = success, 1 = failure
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Environment variable $var is not set"
            all_present=1
        elif [[ "${!var}" == "your_"* ]]; then
            log_error "Environment variable $var still has placeholder value"
            all_present=1
        else
            log_success "Environment variable $var is configured"
        fi
    done
    
    # Check optional but recommended variables
    local optional_vars=("FLASK_ENV" "PORT" "GUNICORN_WORKERS")
    for var in "${optional_vars[@]}"; do
        if [ -n "${!var}" ]; then
            log_success "Optional environment variable $var is set: ${!var}"
        else
            log_warning "Optional environment variable $var is not set"
        fi
    done
    
    return $all_present
}

validate_docker_setup() {
    log_info "Validating Docker setup..."
    
    # Check Docker
    if ! check_executable "docker" "Docker"; then
        return 1
    fi
    
    # Check Docker Compose
    if command -v docker-compose &> /dev/null; then
        check_executable "docker-compose" "Docker Compose"
    elif docker compose version &> /dev/null 2>&1; then
        log_success "Docker Compose (plugin) is available"
        ((CHECKS_PASSED++))
    else
        log_error "Docker Compose is not available"
        return 1
    fi
    
    # Check if Docker daemon is running
    if docker info &> /dev/null; then
        log_success "Docker daemon is running"
    else
        log_error "Docker daemon is not running"
        return 1
    fi
    
    return 0
}

validate_file_structure() {
    log_info "Validating file structure..."
    
    # Required files
    local required_files=(
        "requirements.txt"
        "gunicorn.conf.py"
        "docker-compose.yml"
        "Dockerfile"
        ".dockerignore"
        "deploy.sh"
    )
    
    for file in "${required_files[@]}"; do
        check_file_exists "$file" "Required file"
    done
    
    # Required directories
    local required_dirs=(
        "src"
        "templates"
        "static"
        "config"
    )
    
    for dir in "${required_dirs[@]}"; do
        check_directory_exists "$dir" "Required directory"
    done
    
    # Key application files
    local app_files=(
        "src/app.py"
        "src/wsgi.py"
        "src/routes/health_routes.py"
        "config/config.yaml"
    )
    
    for file in "${app_files[@]}"; do
        check_file_exists "$file" "Application file"
    done
    
    # Check if deploy script is executable
    if [ -x "deploy.sh" ]; then
        log_success "deploy.sh is executable"
    else
        log_warning "deploy.sh is not executable (run: chmod +x deploy.sh)"
    fi
}

validate_python_dependencies() {
    log_info "Validating Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        log_success "requirements.txt found"
        
        # Check if critical dependencies are listed
        local critical_deps=("flask" "gunicorn" "pyyaml" "python-dotenv")
        local missing_deps=()
        
        for dep in "${critical_deps[@]}"; do
            if ! grep -i "^${dep}" requirements.txt >/dev/null 2>&1; then
                missing_deps+=("$dep")
            fi
        done
        
        if [ ${#missing_deps[@]} -eq 0 ]; then
            log_success "All critical dependencies found in requirements.txt"
            return 0
        else
            log_warning "Missing critical dependencies: ${missing_deps[*]}"
            ((WARNINGS++))
            return 1
        fi
    else
        log_error "requirements.txt not found"
        ((CHECKS_FAILED++))
        return 1
    fi
}

validate_configuration() {
    log_info "Validating configuration files..."
    
    # Validate YAML syntax
    if command -v python3 &> /dev/null; then
        if python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))" 2>/dev/null; then
            log_success "config.yaml has valid YAML syntax"
        else
            log_error "config.yaml has invalid YAML syntax"
        fi
    else
        log_warning "Cannot validate YAML syntax (python3 not available)"
    fi
    
    # Check Gunicorn config syntax
    if python3 -m py_compile gunicorn.conf.py 2>/dev/null; then
        log_success "gunicorn.conf.py has valid Python syntax"
    else
        log_error "gunicorn.conf.py has invalid Python syntax"
    fi
}

check_security_settings() {
    log_info "Checking security settings..."
    
    if [ -f ".env" ]; then
        source .env 2>/dev/null || true
        
        # Check SECRET_KEY length
        if [ -n "$SECRET_KEY" ] && [ ${#SECRET_KEY} -ge 32 ]; then
            log_success "SECRET_KEY has adequate length (${#SECRET_KEY} characters)"
        else
            log_warning "SECRET_KEY should be at least 32 characters long"
        fi
        
        # Check if running in production mode
        if [ "$FLASK_ENV" = "production" ]; then
            log_success "Flask environment is set to production"
        else
            log_warning "Flask environment is not set to production"
        fi
        
        # Check for debug mode
        if [ "$FLASK_DEBUG" = "false" ] || [ -z "$FLASK_DEBUG" ]; then
            log_success "Debug mode is disabled"
        else
            log_warning "Debug mode should be disabled in production"
        fi
    fi
}

# Main validation
main() {
    echo "============================================"
    echo "  SeekrAI Production Setup Validation"
    echo "============================================"
    echo
    
    validate_docker_setup
    validate_file_structure
    validate_env_file
    validate_python_dependencies
    validate_configuration
    check_security_settings
    
    echo
    echo "============================================"
    echo "  Validation Summary"
    echo "============================================"
    
    log_info "Checks passed: ${GREEN}$CHECKS_PASSED${NC}"
    
    if [ $WARNINGS -gt 0 ]; then
        log_info "Warnings: ${YELLOW}$WARNINGS${NC}"
    fi
    
    if [ $CHECKS_FAILED -gt 0 ]; then
        log_info "Checks failed: ${RED}$CHECKS_FAILED${NC}"
        echo
        log_error "Setup validation failed. Please fix the issues above before deploying."
        exit 1
    else
        echo
        log_success "All critical checks passed! Your setup is ready for production deployment."
        
        if [ $WARNINGS -gt 0 ]; then
            echo
            log_warning "There are $WARNINGS warnings. Consider addressing them for optimal security and performance."
        fi
        
        echo
        log_info "Next steps:"
        echo "  1. Review any warnings above"
        echo "  2. Run: ./deploy.sh"
        echo "  3. Check health: curl http://localhost:5000/health"
        
        exit 0
    fi
}

# Run validation
main "$@" 