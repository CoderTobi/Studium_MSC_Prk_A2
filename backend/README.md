# Backend

FastAPI backend of the AI supported shopping list. It implements
[`api/openapi.yaml`](../api/openapi.yaml) and stores the items in Firestore following
[`database.md`](../database.md).

**Current state**

| Part | State |
|---|---|
| Items API + Firestore | done |
| Error format, request IDs, CORS, rate limiting, body size limit | done |
| `POST /recommendations` + Ollama | done: prompt validation, injection check, Ollama call, response parsing, rate limit |
| Firebase token verification | not implemented; only the debug mode (`AUTH_DISABLED=true`) exists, otherwise the backend refuses to start |

## Setup

```bash
cd backend
uv sync                      # creates .venv from uv.lock
cp .env.example .env         # then adjust
```

Recommendations need [Ollama](https://ollama.com) on the host OS (not in Docker)
with the configured model pulled:

```bash
ollama pull llama3.2         # or whatever OLLAMA_MODEL is set to
```

From inside a container, Ollama is reached via `host.docker.internal`. On a Linux host,
Ollama listens on `127.0.0.1` only by default, so start it with `OLLAMA_HOST=0.0.0.0`
to make it reachable from containers.

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
curl -X POST localhost:8000/api/v1/recommendations -H 'Content-Type: application/json' \
  -d '{"prompt":"Spaghetti bolognese for four people"}'
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
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/backend/secrets:/app/secrets:ro" shopping-list-backend
```

`--add-host` makes `host.docker.internal` (the default `OLLAMA_URL` in `.env.example`)
resolve to the host on plain Linux Docker; Docker Desktop provides it already.

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
| `OLLAMA_URL` | `http://localhost:11434` | Base URL of the Ollama server |
| `OLLAMA_MODEL` | `llama3.2` | Model used for recommendations |
| `OLLAMA_TIMEOUT_SECONDS` | `30` | Server-side timeout per model call |
| `OLLAMA_MAX_OUTPUT_TOKENS` | `2048` | Max generated tokens per model call, including the thinking of thinking models |
| `OLLAMA_THINK` | (model default) | `false` turns thinking off for thinking models, `true` forces it |

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
├── recommendations.py   recommendation pipeline, model output parsing and validation
├── prompt_guard.py      prompt injection check (PROMPT_REJECTED)
├── ollama.py            Ollama chat API client (system prompt, JSON schema, timeouts)
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

## AI recommendations

`POST /recommendations` runs this pipeline (`recommendations.RecommendationService`):

1. **Prompt validation**: trimmed, length limited (`PROMPT_EMPTY`, `PROMPT_TOO_LONG`).
2. **Injection check** (`prompt_guard.py`, `PROMPT_REJECTED`): rule-based, English and
   German. Rejects instructions aimed at the model ("ignore the previous
   instructions", "you are now ..."), questions about its configuration, chat template
   tokens, fake conversation turns, bidi/control characters and more than 10 lines.
   Text is normalized first (NFKC, zero-width characters removed), so look-alike or
   invisible characters can't hide a keyword. Only the rule name is logged.
3. **Ollama call** (`ollama.py`): `POST /api/chat` with a fixed system prompt, the user
   prompt wrapped in `<meal_request>` tags as data, a JSON schema as `format`
   (structured output) and a cap on generated tokens. No answer within
   `OLLAMA_TIMEOUT_SECONDS` → `AI_TIMEOUT`; unreachable server, unknown model or HTTP
   error → `AI_UNAVAILABLE`.
4. **Response parsing** (`parse_recommendations`): the model output must be
   `{"items": [...]}` (else `AI_INVALID_RESPONSE`). Of each entry only `name` is kept.
   Names are normalized and must pass an allowlist: at most 60 characters, letters,
   digits, spaces and `-'&,.()/%+` only, no URLs or domains. Invalid entries and
   duplicates are dropped, at most 20 recommendations are returned. The raw model
   output is never sent to the client or logged.

Each model call logs the model and its token usage, for example
`Ollama call: model=llama3.2 prompt_tokens=212 output_tokens=58 total_tokens=270 duration_ms=1843`.
