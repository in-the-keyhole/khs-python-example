# Multi-stage build for the FastAPI app.
#
#   Stage 1 (builder): install uv, resolve and install runtime deps into .venv
#   Stage 2 (runtime): copy just the venv + app code into a slim image
#
# Why two stages: the build stage carries uv + caches + build toolchain;
# the runtime image carries only what's needed to serve traffic. Final
# image is ~150 MB instead of ~500 MB.

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

# Grab the uv binary from Astral's official image. Faster and smaller than
# pip-installing it. `--from` copies files from another image at build time.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# uv tuning for containers: don't try to compile bytecode (we do it later),
# don't link the venv to the system Python (it doesn't exist in /usr/bin).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install deps first WITHOUT the project, so this layer caches across code
# changes — `pyproject.toml` and `uv.lock` rarely change, your app code
# does. Re-pull this layer only when deps change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Now copy the app and install the project itself.
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

# Run as non-root. Many corp k8s clusters reject root containers.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Copy the venv + app code from the builder. Nothing else (no uv, no caches).
COPY --from=builder --chown=app:app /app /app

# Put the venv's bin on PATH so `uvicorn` is found without activation.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

# `--host 0.0.0.0` is the container-equivalent of "listen on every interface".
# Default is 127.0.0.1, which inside a container only accepts traffic from
# the container itself — you'd never be able to reach it from the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
