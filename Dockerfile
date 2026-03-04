FROM python:3.11-slim

# Install bcftools and tabix (htslib)
RUN apt-get update && \
    apt-get install -y --no-install-recommends bcftools tabix && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev extras)
RUN uv sync --no-dev --no-install-project

# Copy the rest of the project
COPY . .

# Install the project itself
RUN uv sync --no-dev

# Build the lookup database (baked into the image)
RUN uv run python scripts/build_lookup_db.py

ENTRYPOINT ["uv", "run", "genechat"]
