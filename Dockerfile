# ---- Stage 1: build ------------------------------------------------
FROM python:3.12-slim AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install runtime dependencies only (no dev group)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the source code
COPY . .

# Install the project itself into the venv
RUN uv sync --frozen --no-dev


# ---- Stage 2: runtime ----------------------------------------------
FROM python:3.12-slim AS runtime

# Install git (required by `santai init` to initialize repos)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd --gid 1000 santai \
    && useradd --uid 1000 --gid santai --create-home santai

WORKDIR /app

# Copy the virtual environment and source from the builder
COPY --from=builder /app /app

# Put the venv on the PATH so `santai` is directly callable
ENV PATH="/app/.venv/bin:$PATH"

# Default working directory for santai projects (mountable volume)
RUN mkdir -p /data && chown santai:santai /data
WORKDIR /data

USER santai

# Expose the web dashboard port
EXPOSE 8000

# Default entrypoint — can be overridden in docker-compose
ENTRYPOINT ["santai"]
CMD ["--help"]
