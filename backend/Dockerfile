# Multi-stage Dockerfile using uv (fast Python package manager)
# Stage 1: builder — install deps
# Stage 2: runtime — minimal image with only what we need

# === STAGE 1: Builder ===
FROM python:3.12-slim AS builder

# Install uv (fast package manager — our differentiator vs other teams)
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# Copy only dependency files first (for Docker layer caching)
COPY pyproject.toml ./

# Install dependencies into a virtualenv inside the image
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -r pyproject.toml

# === STAGE 2: Runtime ===
FROM python:3.12-slim AS runtime

# System deps for ML libraries (libgomp for XGBoost, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Non-root user (security best practice)
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copy app code
COPY --chown=app:app . .

# Make sure data dirs exist
RUN mkdir -p data/models data/mock data/audio_samples

EXPOSE 8000

# Healthcheck — Docker uses this to know if container is healthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
# --reload disabled in container (use volume mounts + reload in dev)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
