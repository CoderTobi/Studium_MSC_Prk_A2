/**
 * Helpers for the debug mode. NOT authentication: anybody can create these tokens.
 * They only work with a backend running with `AUTH_DISABLED=true`.
 */

/**
 * Allowed debug usernames. Stricter than the backend (which accepts any printable uid
 * without `/`), so a username can always be used as a Firestore document ID.
 */
export const DEBUG_USERNAME_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

export function validateDebugUsername(username: string): string | null {
	if (!username.trim()) return 'Please enter a username.';
	if (!DEBUG_USERNAME_PATTERN.test(username.trim())) {
		return 'Use 1–64 letters, digits, "-" or "_".';
	}
	return null;
}

function base64Url(text: string): string {
	let binary = '';
	for (const byte of new TextEncoder().encode(text)) binary += String.fromCharCode(byte);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * Builds an unsigned JWT (`alg: none`) whose `sub` claim is the uid. In debug mode the
 * backend reads `sub` without checking the signature, just like it would read the
 * uid from a real Firebase ID token.
 */
export function createDebugToken(uid: string): string {
	const header = base64Url(JSON.stringify({ alg: 'none', typ: 'JWT' }));
	const payload = base64Url(JSON.stringify({ sub: uid }));
	return `${header}.${payload}.`;
}
