# Production image of the backend.
#
# Build:  docker build -t shopping-list-backend backend/
# Run:    see backend/README.md (needs the env vars from .env.example and the
#         Firestore service account key mounted read-only).

# ---- build stage: resolve and install dependencies with uv -------------------
FROM python:3.13-slim-trixie AS build

# eMudhra certificate incident: enforce pip >= 26.2.2 and uv >= 0.13.4.
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2.2"
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first, so this layer is cached while only the source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --no-editable


# ---- runtime stage: only the virtual environment, no build tools -------------
FROM python:3.13-slim-trixie AS runtime

RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2.2" \
    && useradd --system --no-create-home --uid 10001 app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=build /app/.venv /app/.venv

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"]

# Access logging is done by the app itself (with request IDs), so uvicorn's is off.
CMD ["uvicorn", "shopping_list.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
