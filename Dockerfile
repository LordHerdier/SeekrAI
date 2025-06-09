# Multi-stage build for production optimization
FROM python:3.11-slim AS builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION=1.0.0

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim AS production

# Set labels
LABEL maintainer="SeekrAI Team"
LABEL version="${VERSION}"
LABEL description="SeekrAI - AI-powered resume analysis and job search platform"
LABEL build-date="${BUILD_DATE}"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    PYTHONPATH=/app/src

# Create non-root user for security
RUN groupadd -r seekrai && useradd -r -g seekrai seekrai

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/seekrai/.local

# Copy application code
COPY --chown=seekrai:seekrai . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/uploads /app/job_results /app/.cache /app/logs /app/temp && \
    chown -R seekrai:seekrai /app && \
    chmod -R 755 /app && \
    chmod -R 777 /app/uploads /app/job_results /app/.cache /app/logs /app/temp

# Update PATH to include user packages
ENV PATH=/home/seekrai/.local/bin:$PATH

# Switch to non-root user
USER seekrai

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command - use gunicorn for production
CMD ["gunicorn", "--config", "gunicorn.conf.py", "src.wsgi:application"] 