# PENNY Project - Azure ML Production Dockerfile
# Civic Engagement AI - Secure Container Build

# Use official slim Python base for smaller image size
FROM python:3.10-slim

# Set metadata labels for container identification
LABEL maintainer="PENNY Project"
LABEL description="Civic Engagement AI - Azure ML Production Container"
LABEL version="2.0"

# Set working directory
WORKDIR /code

# Prevent Python bytecode generation + enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set production environment variable
ENV ENVIRONMENT=production

# Create non-root user for security (Azure best practice)
RUN useradd --create-home --shell /bin/bash pennyuser && \
    chown -R pennyuser:pennyuser /code

# Install system dependencies (if needed for future ML libraries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements FIRST for Docker layer caching optimization
COPY --chown=pennyuser:pennyuser requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories with proper permissions
RUN mkdir -p /code/logs /code/data /code/models && \
    chown -R pennyuser:pennyuser /code

# Copy application code (exclude .env - use Azure Key Vault instead)
COPY --chown=pennyuser:pennyuser app/ ./app/
COPY --chown=pennyuser:pennyuser models/ ./models/
COPY --chown=pennyuser:pennyuser data/ ./data/
COPY --chown=pennyuser:pennyuser README.md ./README.md

# ⚠️ CRITICAL: DO NOT copy .env file to container
# Secrets should be injected via Azure Key Vault or environment variables at runtime
# If .env is needed locally, mount it as a volume during development only

# Switch to non-root user (security hardening)
USER pennyuser

# Health check endpoint (FastAPI automatic /docs or custom /health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port 8000 for FastAPI
EXPOSE 8000

# Start application with uvicorn
# Using 4 workers for production concurrency (adjust based on container size)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info"]