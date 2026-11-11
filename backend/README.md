# Backend

FastAPI backend of the AI supported shopping list. It implements
[`api/openapi.yaml`](../api/openapi.yaml) and stores the items in Firestore following
[`database.md`](../database.md).

**Current state**

| Part | State |
|---|---|
| Items API + Firestore | done |
| Error format, request IDs, CORS, rate limiting, body size limit | done |
| `POST /recommendations` | prompt validation and rate limit done; always answers `503 AI_UNAVAILABLE` because there is no Ollama connection yet |
| Firebase token verification | not implemented; only the debug mode (`AUTH_DISABLED=true`) exists, otherwise the backend refuses to start |

## Setup

```bash
cd backend
uv sync                      # creates .venv from uv.lock
cp .env.example .env         # then adjust
```

Firestore access needs a service account key:
Firebase console → Project settings → Service accounts → *Generate new private key*.
Save it as `backend/secrets/firebase-service-account.json`. The `secrets/` folder is
gitignored, never commit the key.

No schema setup is needed in Firestore. The `users/{uid}` document and its `items`
subcollection are created with the first item, and no composite indexes are required.

## Run

```bash
uv run --env-file .env uvicorn shopping_list.main:create_app --factory --reload --port 8000
```

Then try it out (in debug mode without a token, everything belongs to `debug-user`):

```bash
curl localhost:8000/api/v1/health
curl -X POST localhost:8000/api/v1/items -H 'Content-Type: application/json' -d '{"name":"Milk"}'
curl localhost:8000/api/v1/items
```

To act as another user in debug mode, send any JWT-shaped token whose payload has a
`sub` claim. The signature isn't checked:

```bash
TOKEN="e30.$(printf '{"sub":"alice"}' | base64 | tr '+/' '-_' | tr -d '=').x"
curl localhost:8000/api/v1/items -H "Authorization: Bearer $TOKEN"
```

## Tests and linting

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

The API tests use an in-memory repository. The Firestore integration tests in
`tests/test_firestore_repository.py` only run when `FIRESTORE_EMULATOR_HOST` points to a
running Firestore emulator; otherwise they are skipped.

## Docker

```bash
docker build -t shopping-list-backend backend/
docker run --rm -p 8000:8000 --env-file backend/.env \
  -v "$PWD/backend/secrets:/app/secrets:ro" shopping-list-backend
```

The container runs as an unprivileged user (uid 10001), so the key file must be readable
by it (for example `chmod 644`, or mount it with matching ownership).

## Configuration

All options are environment variables. See [`.env.example`](.env.example) for the
full list with defaults. The most important ones:

| Variable | Default | Meaning |
|---|---|---|
| `AUTH_DISABLED` | `false` | Debug mode, tokens are not verified. Currently required to be `true`. |
| `GOOGLE_APPLICATION_CREDENTIALS` | (none) | Path to the service account key file |
| `GOOGLE_CLOUD_PROJECT` | from the key | Firebase/GCP project ID |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database name |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated frontend origins |
| `ITEM_LIMIT` | `200` | Max items per user |
| `RATE_LIMIT_GENERAL_PER_MINUTE` / `RATE_LIMIT_AI_PER_MINUTE` | `60` / `10` | Per-user rate limits |

## Code structure

```
src/shopping_list/
├── main.py              create_app(): wiring, middleware order, routers
├── config.py            Settings from environment variables
├── errors.py            ErrorCode, ApiError, uniform JSON error responses
├── middleware.py        request ID, CORS, 500 guard, body size limit
├── auth.py              Authorization header → uid (debug mode only for now)
├── rate_limit.py        in-memory per-uid rate limiter (general + ai buckets)
├── models.py            request/response schemas from openapi.yaml
├── dependencies.py      JSON body parsing, repository/service providers
├── repository.py        ItemRepository protocol + Firestore implementation
├── recommendations.py   prompt validation, AIClient protocol (Ollama comes later)
├── logging_setup.py     log format with request ID (no prompts/bodies logged)
├── request_context.py   request ID context variable
└── routers/             health, items, recommendations
```

Every request passes through these layers in order:

1. middleware (request ID, CORS, body size)
2. authentication (`get_current_uid`)
3. rate limit
4. body validation (`json_body`)
5. handler
6. repository or service

Expected errors are raised as `ApiError(ErrorCode.X)` anywhere in that chain.
