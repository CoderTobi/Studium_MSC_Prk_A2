/**
 * Environment variables of the frontend.
 *
 * They are read when the server starts (not at build time), so the same build or
 * Docker image works with any backend URL. SvelteKit validates them on startup and
 * passes the public ones to the browser via `$app/env/public`.
 * See `.env.example` for an example configuration.
 */
import { defineEnvVars } from '@sveltejs/kit/env';
import { parseAuthMode, parseBackendUrl, parseFirebaseApiKey } from '#lib/config/parse.ts';

export const variables = defineEnvVars({
	PUBLIC_BACKEND_URL: {
		public: true,
		description: 'Base URL of the backend without /api/v1, for example http://localhost:8000',
		schema: parseBackendUrl
	},
	PUBLIC_AUTH_MODE: {
		public: true,
		description:
			'How users sign in: "firebase" (email and password) or "debug" (no real authentication).',
		schema: parseAuthMode
	},
	PUBLIC_FIREBASE_API_KEY: {
		public: true,
		description: 'Web API key of the Firebase project. Required for PUBLIC_AUTH_MODE=firebase.',
		schema: parseFirebaseApiKey
	}
});
