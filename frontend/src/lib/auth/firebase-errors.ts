/**
 * User-safe messages for the errors of Firebase Authentication. Firebase's own messages
 * are technical ("Firebase: Error (auth/invalid-credential).") and are never shown.
 */

/** The same as Firebase's default minimum password length. */
export const PASSWORD_MIN_LENGTH = 6;

const MESSAGES: Record<string, string> = {
	// Firebase does not say whether the email or the password was wrong.
	'auth/invalid-credential': 'Wrong email or password.',
	'auth/wrong-password': 'Wrong email or password.',
	'auth/user-not-found': 'Wrong email or password.',
	'auth/invalid-email': 'Please enter a valid email address.',
	'auth/missing-email': 'Please enter a valid email address.',
	'auth/missing-password': 'Please enter your password.',
	'auth/user-disabled': 'This account has been disabled.',
	'auth/email-already-in-use': 'An account with this email address already exists.',
	'auth/weak-password': `The password must have at least ${PASSWORD_MIN_LENGTH} characters.`,
	'auth/password-does-not-meet-requirements': 'The password does not meet the requirements.',
	'auth/too-many-requests': 'Too many attempts. Please try again later.',
	'auth/network-request-failed':
		'Could not reach the sign-in service. Please check your connection.',
	'auth/operation-not-allowed': 'Signing in with email and password is not enabled.'
};

const FALLBACK = 'Something went wrong. Please try again.';

export function firebaseErrorMessage(error: unknown): string {
	const code =
		typeof error === 'object' && error !== null && 'code' in error ? error.code : undefined;
	return (typeof code === 'string' && Object.hasOwn(MESSAGES, code) && MESSAGES[code]) || FALLBACK;
}
