/**
 * Parsers for the frontend's environment variables.
 *
 * They are pure functions so they can be unit tested and used from `src/env.ts`,
 * which SvelteKit evaluates at startup to validate the configuration.
 */

export const AUTH_MODES = ['debug'] as const;
/**
 * How users sign in.
 * - `debug`: no real authentication. Works only with a backend that runs with
 *   `AUTH_DISABLED=true`. Never use in production.
 *
 * `firebase` will be added together with Firebase Authentication.
 */
export type AuthMode = (typeof AUTH_MODES)[number];

/**
 * Validates the backend base URL (without the `/api/v1` suffix) and removes trailing
 * slashes, so that paths can simply be appended.
 */
export function parseBackendUrl(value: string | undefined): string {
	const raw = value?.trim();
	if (!raw) {
		throw new Error('PUBLIC_BACKEND_URL must be set, for example http://localhost:8000');
	}

	let url: URL;
	try {
		url = new URL(raw);
	} catch {
		throw new Error(`PUBLIC_BACKEND_URL is not a valid URL: ${raw}`);
	}
	if (url.protocol !== 'http:' && url.protocol !== 'https:') {
		throw new Error('PUBLIC_BACKEND_URL must use http or https');
	}
	if (url.search || url.hash || url.username || url.password) {
		throw new Error('PUBLIC_BACKEND_URL must not contain credentials, a query or a fragment');
	}

	return url.href.replace(/\/+$/, '');
}

export function parseAuthMode(value: string | undefined): AuthMode {
	const raw = value?.trim();
	const mode = AUTH_MODES.find((candidate) => candidate === raw);
	if (!mode) {
		throw new Error(
			`PUBLIC_AUTH_MODE must be one of: ${AUTH_MODES.join(', ')} (got "${raw ?? ''}")`
		);
	}
	return mode;
}
