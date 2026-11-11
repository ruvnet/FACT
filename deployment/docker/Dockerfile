# FACT System Production Dockerfile
# Multi-stage build for optimized production image

# Debian 11 (bullseye) is EOL; its security archive no longer serves packages.
FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r fact && useradd -r -g fact fact

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-security.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-security.txt

# Development stage
FROM base AS development

# Install development dependencies
COPY requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements-test.txt

# Copy source code
COPY --chown=fact:fact . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/output && \
    chown -R fact:fact /app

USER fact

EXPOSE 8000

CMD ["python", "main.py"]

# Production stage
FROM base AS production

# Copy only necessary files
COPY --chown=fact:fact src/ ./src/
COPY --chown=fact:fact scripts/ ./scripts/
COPY --chown=fact:fact main.py ./
COPY --chown=fact:fact .env.example ./

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/output && \
    chown -R fact:fact /app

# Security hardening
# (directories need the execute bit or the package cannot be imported)
RUN chmod 755 /app && \
    find /app/src -type d -exec chmod 755 {} + && \
    find /app/src -type f -exec chmod 644 {} + && \
    chmod 755 /app/main.py

USER fact

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "main.py"]