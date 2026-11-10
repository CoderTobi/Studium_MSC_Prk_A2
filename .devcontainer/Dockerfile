# Development image only — the production images live in backend/ and frontend/.
FROM mcr.microsoft.com/devcontainers/python:2-3.13-trixie

# uv: Python package/venv manager (pyproject.toml + uv.lock)
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /usr/local/bin/
