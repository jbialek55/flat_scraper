FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first for better Docker layer caching
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Install Chromium and its system dependencies for Playwright
RUN uv run playwright install --with-deps chromium

# Copy source code and install the package
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Directories for SQLite database and logs (mounted as volumes)
RUN mkdir -p /app/data /app/logs

CMD ["uv", "run", "python", "-m", "flat_scraper.scheduler"]
