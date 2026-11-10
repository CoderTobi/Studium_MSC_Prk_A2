#!/usr/bin/env bash
# Runs once after the dev container is created.
set -euo pipefail

# Install dependencies once the projects exist (safe to run before scaffolding).
if [ -f backend/pyproject.toml ]; then
  (cd backend && uv sync)
fi
if [ -f frontend/package.json ]; then
  (cd frontend && npm install)
fi

echo
echo "Tool versions:"
python --version
uv --version
node --version
npm --version
