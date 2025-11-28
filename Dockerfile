# PENNY Project - Production Dockerfile
# Civic Engagement AI - Container Build for Hugging Face Spaces

# Use official slim Python base for smaller image size
FROM python:3.10-slim

# Set metadata labels for container identification
LABEL maintainer="PENNY Project"
LABEL description="Civic Engagement AI - Production Container"
LABEL version="2.0"

# Set working directory
WORKDIR /code

# Prevent Python bytecode generation + enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set production environment variable
ENV ENVIRONMENT=production

# Install system dependencies (if needed for future ML libraries)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements FIRST for Docker layer caching optimization
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /code/logs /code/data /code/models

# Copy application code (exclude .env - use environment variables instead)
COPY app.py ./
COPY app/ ./app/
COPY models/ ./models/
COPY data/ ./data/
COPY README.md ./README.md

# ⚠️ CRITICAL: DO NOT copy .env file to container
# Secrets should be injected via environment variables at runtime

# Health check endpoint (FastAPI automatic /docs or custom /health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port 8000 for FastAPI
EXPOSE 8000

# Start application with uvicorn
# Using single worker for Hugging Face Spaces resource constraints
# Port and workers can be overridden via environment variables if needed
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1} --log-level info"]