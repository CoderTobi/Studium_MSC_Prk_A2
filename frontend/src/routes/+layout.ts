import { auth } from '#lib/services.ts';

/**
 * The whole app is rendered in the browser (single-page app):
 * - the Firebase JS SDK, which will handle sign-in, only runs in the browser, and
 * - all data comes from the backend with the user's token, so there is nothing
 *   useful to render on the server.
 */
export const ssr = false;

/** Restores the session before any page renders, so route guards can rely on `auth.user`. */
export async function load() {
	await auth.init();
}
