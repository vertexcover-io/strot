FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy strot source code first
COPY strot/ ./strot/
COPY pyproject.toml ./

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install strot package directly with pip
RUN uv pip install --system .

# Copy migration files and alembic config from api directory
COPY api/migration/ ./migration/
COPY api/alembic.ini ./

# Copy API project files
COPY api/ ./api/

# Change to API directory
WORKDIR /app/api

# Install API dependencies with pip
RUN uv pip install --system .

# Install chromium
RUN playwright install chromium --with-deps

# Expose port for the server
EXPOSE 1337

# Create startup script
RUN echo '#!/bin/bash\nset -e\necho "Running database migrations..."\ncd /app && alembic upgrade head\necho "Starting API server..."\ncd /app/api && python -m uvicorn strot_api.main:app --host 0.0.0.0 --port 1337' > /start.sh
RUN chmod +x /start.sh

# Run migrations and start server
CMD ["/start.sh"]
