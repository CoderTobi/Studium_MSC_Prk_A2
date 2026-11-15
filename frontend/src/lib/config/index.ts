import { PUBLIC_AUTH_MODE, PUBLIC_BACKEND_URL, PUBLIC_FIREBASE_API_KEY } from '$app/env/public';
import { requireFirebaseApiKey } from './parse.ts';

export type { AuthMode } from './parse';

/** Validated runtime configuration (see `src/env.ts`). */
export const config = {
	/** Base URL of the backend, without trailing slash and without `/api/v1`. */
	backendUrl: PUBLIC_BACKEND_URL,
	/** Base URL of the versioned REST API. */
	apiBaseUrl: `${PUBLIC_BACKEND_URL}/api/v1`,
	authMode: PUBLIC_AUTH_MODE,
	/** Web API key of the Firebase project, or `null` if the auth mode is not `firebase`. */
	firebaseApiKey: requireFirebaseApiKey(PUBLIC_AUTH_MODE, PUBLIC_FIREBASE_API_KEY)
} as const;
