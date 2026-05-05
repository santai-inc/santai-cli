# Santai CLI — lightweight image installing from PyPI
FROM python:3.12-slim

# Install system dependencies (git is required by `santai init`)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install santai-cli from PyPI
RUN pip install --no-cache-dir santai-cli

# Create a non-root user
RUN groupadd --gid 1000 santai \
    && useradd --uid 1000 --gid santai --create-home santai

# Default working directory for santai projects (mountable volume)
RUN mkdir -p /data && chown santai:santai /data
WORKDIR /data

USER santai

# Expose the web dashboard port
EXPOSE 8000

# Default entrypoint — override command via docker compose
ENTRYPOINT ["santai"]
CMD ["--help"]
