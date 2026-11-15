import type { AuthMode } from '#lib/config/parse.ts';

export interface AuthUser {
	/** Stable user ID. The backend takes it from the token, never from the frontend. */
	uid: string;
	/** Name to show in the UI. */
	displayName: string;
}

/** Why the user was signed out. Lets the login page explain an unexpected sign-out. */
export type SignOutReason = 'user' | 'session-expired';

/**
 * What the rest of the app needs from authentication. Pages, the route guard and the
 * API client only use this interface, so a Firebase implementation can be added
 * without changing them.
 *
 * Signing in is not part of it, because every implementation signs in differently
 * (username in debug mode, email/password or Google with Firebase). Each mode has
 * its own sign-in form, see `routes/login`.
 */
export interface AuthService {
	readonly mode: AuthMode;
	/** The signed-in user, or `null`. Reactive. */
	readonly user: AuthUser | null;
	/** Reason of the last sign-out, or `null` after signing in. Reactive. */
	readonly signOutReason: SignOutReason | null;
	/** Restores a persisted session. Must finish before `user` is meaningful. */
	init(): Promise<void>;
	/** Current ID token for the `Authorization` header, or `null` if signed out. */
	getIdToken(): Promise<string | null>;
	signOut(reason?: SignOutReason): Promise<void>;
}
