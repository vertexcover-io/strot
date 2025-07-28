FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files first for better caching
COPY pyproject.toml ./
RUN touch README.md
COPY api/pyproject.toml ./api/
RUN touch api/README.md

# Copy strot package and install it
COPY strot/ ./strot/
RUN uv pip install --no-cache-dir .

# Install API dependencies
WORKDIR /build/api
RUN uv pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Install playwright chromium headless shell only
RUN /opt/venv/bin/playwright install --only-shell --with-deps chromium

# Copy application code
COPY api/ ./api/

# Set working directory to API
WORKDIR /app/api

# Expose port
EXPOSE 1337

# Create startup script
RUN printf '#!/bin/sh\n\
set -e\n\
echo "Running database migrations..."\n\
/opt/venv/bin/alembic upgrade head\n\
echo "Starting API server..."\n\
/opt/venv/bin/uvicorn strot_api.main:app --host 0.0.0.0 --port 1337\n' > /start.sh && \
    chmod +x /start.sh

CMD ["/start.sh"]
