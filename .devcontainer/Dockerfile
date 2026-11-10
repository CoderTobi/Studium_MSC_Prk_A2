# Development image only — the production images live in backend/ and frontend/.
FROM mcr.microsoft.com/devcontainers/python:2-3.13-trixie

# The base image ships pip 25.2, whose vendored CA bundle predates the eMudhra
# certificate incident. Enforce a fixed pip version.
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2.2"

# uv: Python package/venv manager (pyproject.toml + uv.lock)
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /usr/local/bin/

# create the folder ahead of time so the volume is owned by vscode and not root. Otherwise Claude can't write to it
RUN mkdir -p /home/vscode/.claude && chown -R vscode:vscode /home/vscode/.claude