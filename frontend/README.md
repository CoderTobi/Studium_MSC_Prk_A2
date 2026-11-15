# Frontend

SvelteKit frontend of the AI supported shopping list. It talks only to the backend,
through the API defined in [`api/openapi.yaml`](../api/openapi.yaml). It never talks to
Ollama.

**Tech:** SvelteKit 3 (Svelte 5 runes), TypeScript, Tailwind CSS 4, `adapter-node`.
Single-page app: server-side rendering is off, the small Node server only delivers
the app shell and the configuration.

**Current state**

| Part                                                             | State                                                                      |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Shopping list (list, add, remove)                                | done                                                                       |
| AI recommendations (prompt, select, accept, discard, disclaimer) | done                                                                       |
| Error handling for all API error codes                           | done                                                                       |
| Impressum                                                        | done, with **fictitious placeholder data** in `src/lib/legal/impressum.ts` |
| Authentication                                                   | done: Firebase Authentication (email and password), plus a debug mode      |

## Setup

```bash
cd frontend
npm install
cp .env.example .env         # then adjust
```

## Run

Start the backend first (see [backend/README.md](../backend/README.md)), then:

```bash
npm run dev                  # http://localhost:5173
```

After that you should be able to acces it from the browser in VS Code.
If you want to open it in a different browser on the host and can't acces the page, you might need to start it in host mode instead:

```bash
npm run dev:host                  # http://localhost:5173
```

With `PUBLIC_AUTH_MODE=firebase` you sign in or create an account with email and
password, see [Authentication](#authentication).

Production build:

```bash
npm run build
node --env-file=.env build   # port 3000
```

## Configuration

Environment variables, read **when the server starts**, not at build time. They are
declared and validated in [`src/env.ts`](src/env.ts). The server refuses to start
with an invalid value.

| Variable                  | Example                 | Meaning                                                                                                         |
| ------------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| `PUBLIC_BACKEND_URL`      | `http://localhost:8000` | Backend base URL, **without** `/api/v1`                                                                         |
| `PUBLIC_AUTH_MODE`        | `firebase`              | How users sign in: `firebase` (email and password) or `debug` (no real authentication, never use in production) |
| `PUBLIC_FIREBASE_API_KEY` | `AIza…`                 | Web API key of the Firebase project. Required for `PUBLIC_AUTH_MODE=firebase`                                   |
| `PORT`, `HOST`            | `3000`, `0.0.0.0`       | Only for `node build`, see [adapter-node](https://svelte.dev/docs/kit/adapter-node)                             |

The backend must allow the frontend's origin in `CORS_ALLOWED_ORIGINS`
(`http://localhost:5173` for `npm run dev`, `http://localhost:3000` for `node build`).

## Scripts

| Command                           | What it does                                                 |
| --------------------------------- | ------------------------------------------------------------ |
| `npm run dev`                     | Dev server with hot reload                                   |
| `npm run build`                   | Production build into `build/`                               |
| `npm run check`                   | Type check (svelte-check)                                    |
| `npm run lint` / `npm run format` | Prettier + ESLint / auto-format                              |
| `npm test`                        | Unit tests (Vitest)                                          |
| `npm run gen:api`                 | Regenerate `src/lib/api/schema.d.ts` from `api/openapi.yaml` |

After changing `api/openapi.yaml`, run `npm run gen:api` and `npm run check`. The
compiler then points to every place that has to follow the change.

## Code structure

```
src/
├── env.ts                     runtime environment variables (validated on startup)
├── hooks.server.ts            security headers, CSP connect-src (backend URL, Firebase)
├── lib/
│   ├── config/                parsing + typed access to the configuration
│   ├── api/                   the only code that knows about HTTP
│   │   ├── schema.d.ts        generated from openapi.yaml, do not edit
│   │   ├── types.ts           readable aliases for the generated types
│   │   ├── client.ts          fetch wrapper: base URL, token, timeouts, error parsing
│   │   ├── errors.ts          ApiError + client-side error codes
│   │   ├── validate.ts        runtime checks of successful responses
│   │   ├── items.ts, recommendations.ts   one function per endpoint
│   │   └── limits.ts          API limits for instant feedback in forms
│   ├── auth/                  AuthService interface, Firebase + debug implementation
│   ├── services.ts            composition root: creates auth + api and wires them
│   ├── stores/                page state as Svelte 5 rune classes
│   ├── components/            UI components (layout, items, recommendations, auth)
│   └── legal/impressum.ts     Impressum data
└── routes/
    ├── +layout.ts             ssr = false, restores the session
    ├── (app)/                 everything that needs a signed-in user (route guard)
    │   └── +page.svelte       shopping list + AI panel
    ├── login/                 sign-in page (one form per auth mode)
    ├── impressum/             legal notice (public)
    └── health/                liveness check for the container
```

Imports inside the app use the `#lib/…` subpath import (SvelteKit 3's replacement for
`$lib`) with explicit file extensions, for example `#lib/api/index.ts`.

### How a request flows

1. A component calls a store method (for example `list.add(name)`).
2. The store calls the API function (`api.items.create`).
3. `ApiClient` adds `Authorization: Bearer <token>` from `auth.getIdToken()` and
   sends the request with a timeout: 15 s, or 45 s for recommendations, which is
   longer than the backend's 30 s Ollama timeout.
4. Every failure becomes an `ApiError` with the API's `code`, or one of the
   client-side codes `NETWORK_ERROR`, `CLIENT_TIMEOUT` or `INVALID_RESPONSE`. The UI
   shows the backend's user-safe `message`, a retry hint for `429`, and the
   `requestId`.
5. A `401 UNAUTHENTICATED` signs the user out. The route guard in
   `(app)/+layout.svelte` then redirects to `/login`.

### AI recommendations

- Suggestions are shown in a violet, dashed "AI suggestions" panel with an AI badge,
  and accepted items keep an AI badge in the list (`source: ai_recommendation`).
- A note that AI may make mistakes is always visible in the AI panel. Together with
  suggestions, the backend's `disclaimer` text is shown.
- Accepting sends all selected suggestions in one atomic `POST /items/batch`.
  Discarding happens only in the frontend.
- Item names and suggestions are always rendered as text, never as HTML.

## Authentication

`PUBLIC_AUTH_MODE` selects one of two implementations of the `AuthService` interface
(`src/lib/auth/types.ts`). The API client, the stores and the pages only use that
interface.

### `firebase`

Users sign in with email and password, or create an account on the login page.

Setup:

1. In the Firebase console, enable the **Email/Password** provider (Authentication >
   Sign-in method).
2. Copy the web API key (Project settings > General > Your apps > Web app > `apiKey`)
   into `PUBLIC_FIREBASE_API_KEY` in `.env`. The key is not a secret, every browser
   that opens the app receives it, but it still belongs in `.env` and not in git.
3. Run the backend with `AUTH_DISABLED=false` for the **same** Firebase project.

How it works:

- `src/lib/auth/firebase-sdk.ts` is the only file that imports the Firebase JS SDK
  (`firebase/app` and `firebase/auth`). It is loaded on demand, so the debug mode
  never downloads it.
- Firebase keeps the session in the browser (IndexedDB) until the user signs out,
  and refreshes the ID token, which is valid for one hour, by itself.
- `FirebaseAuthService.getIdToken()` returns that token for the `Authorization`
  header. The backend verifies it on every request.
- Firebase's error codes are mapped to user-safe messages in
  `src/lib/auth/firebase-errors.ts`. A wrong email and a wrong password give the same
  message.
- The browser talks to `https://identitytoolkit.googleapis.com` (sign-in, sign-up)
  and `https://securetoken.googleapis.com` (token refresh). Both are added to the
  CSP's `connect-src` in `src/hooks.server.ts`, only in this mode.
- There is no password reset and no email verification.

### `debug`

You sign in with any username (letters, digits, `-`, `_`), without a password. Each
username has its own list. This needs a backend running with `AUTH_DISABLED=true`
and must never be used in production.

## Tests

```bash
npm test
```

The unit tests cover the API client (headers, error parsing, timeouts, network
errors, invalid responses), the endpoint functions, the limits, the Firebase auth
service (with a fake SDK) and its error messages, the debug token and auth service, the configuration parsing, and both stores (with a fake API).

## Docker

```bash
docker build -t shopping-list-frontend frontend/
docker run --rm -p 3000:3000 \
  -e PUBLIC_BACKEND_URL=http://localhost:8000 \
  -e PUBLIC_AUTH_MODE=firebase -e PUBLIC_FIREBASE_API_KEY=<web API key> \
  shopping-list-frontend
```

The image contains only the self-contained server bundle (no `node_modules`), runs as
the unprivileged `node` user and has a healthcheck on `/health`.
`PUBLIC_BACKEND_URL` is the URL **the browser** uses to reach the backend, not a
Docker-internal host name.
