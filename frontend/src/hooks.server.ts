import type { Handle } from '@sveltejs/kit/hooks';
import { dev } from '$app/env';
import { PUBLIC_AUTH_MODE, PUBLIC_BACKEND_URL, PUBLIC_FIREBASE_API_KEY } from '$app/env/public';
import { requireFirebaseApiKey } from '#lib/config/parse.ts';

// Refuse to start with the `firebase` auth mode but without its API key.
requireFirebaseApiKey(PUBLIC_AUTH_MODE, PUBLIC_FIREBASE_API_KEY);

/**
 * Endpoints the Firebase Authentication SDK calls from the browser: sign-in and
 * sign-up, and refreshing the ID token.
 */
const FIREBASE_AUTH_ORIGINS = [
	'https://identitytoolkit.googleapis.com',
	'https://securetoken.googleapis.com'
];

/**
 * Security headers for the pages served by this server. The CSP itself is configured
 * in `vite.config.ts`. Only `connect-src` is added here, because it must allow the
 * backend URL and depends on the auth mode, which are only known at runtime.
 */
const SECURITY_HEADERS: Record<string, string> = {
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'strict-origin-when-cross-origin',
	'X-Frame-Options': 'DENY',
	'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()'
};

function connectSrc(): string {
	const sources = ["'self'", new URL(PUBLIC_BACKEND_URL).origin];
	if (PUBLIC_AUTH_MODE === 'firebase') sources.push(...FIREBASE_AUTH_ORIGINS);
	// Vite's dev server uses a WebSocket for hot module replacement.
	if (dev) sources.push('ws:', 'wss:');
	return sources.join(' ');
}

export const handle: Handle = async ({ event, resolve }) => {
	const response = await resolve(event);

	for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
		if (!response.headers.has(name)) response.headers.set(name, value);
	}

	const csp = response.headers.get('Content-Security-Policy');
	if (csp && !/(^|;)\s*connect-src\b/.test(csp)) {
		response.headers.set('Content-Security-Policy', `${csp}; connect-src ${connectSrc()}`);
	}

	return response;
};
