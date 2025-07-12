FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install uv from registry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY . .

# Install dependencies using uv
RUN uv sync

# Install chromium browser for playwright
RUN uv run playwright install chromium --with-deps

# Expose port for the server
EXPOSE 1337

# Run the server
CMD ["uv", "run", "ayejax", "serve"]
