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

# Copy strot package pyproject.toml and install dependencies & browser
COPY pyproject.toml ./
RUN touch README.md
RUN uv pip install --no-cache-dir .
RUN /opt/venv/bin/playwright install chromium-headless-shell

# Copy strot package and install it
COPY strot/ ./strot/
RUN uv pip install --no-cache-dir .

# Install API dependencies
WORKDIR /build/api
COPY api/pyproject.toml ./
RUN touch README.md
RUN uv pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy browser from builder and install its dependencies
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright
RUN /opt/venv/bin/playwright install-deps chromium-headless-shell

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
