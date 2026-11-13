/**
 * Composition root: creates the app-wide services and wires them together.
 *
 * Only import this from browser code (pages, components, universal load functions).
 * Server-side rendering is disabled for the whole app (`routes/+layout.ts`).
 */
import { createApi } from '#lib/api/index.ts';
import { createAuthService } from '#lib/auth/index.ts';
import { config } from '#lib/config/index.ts';

export const auth = createAuthService(config.authMode);

export const api = createApi({
	baseUrl: config.apiBaseUrl,
	getToken: () => auth.getIdToken(),
	// The token is missing, invalid or expired. Signing out makes the route guard
	// redirect to the login page.
	onUnauthenticated: () => void auth.signOut('session-expired')
});
