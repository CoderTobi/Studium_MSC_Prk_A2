import type { Handle } from '@sveltejs/kit/hooks';
import { dev } from '$app/env';
import { PUBLIC_BACKEND_URL } from '$app/env/public';

/**
 * Security headers for the pages served by this server. The CSP itself is configured
 * in `vite.config.ts`. Only `connect-src` is added here, because it must allow the
 * backend URL, which is only known at runtime.
 *
 * When Firebase Authentication is added, its endpoints (for example
 * `https://identitytoolkit.googleapis.com` and `https://securetoken.googleapis.com`)
 * must be added to `connect-src` as well.
 */
const SECURITY_HEADERS: Record<string, string> = {
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'strict-origin-when-cross-origin',
	'X-Frame-Options': 'DENY',
	'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()'
};

function connectSrc(): string {
	const sources = ["'self'", new URL(PUBLIC_BACKEND_URL).origin];
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
