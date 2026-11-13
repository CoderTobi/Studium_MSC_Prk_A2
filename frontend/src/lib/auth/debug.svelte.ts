import type { AuthService, AuthUser, SignOutReason } from './types';
import { createDebugToken, validateDebugUsername } from './debug-token';

const STORAGE_KEY = 'shopping-list.debug-username';

/** `localStorage`, or `null` where it is unavailable (server, private mode, blocked). */
function getStorage(): Storage | null {
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

/**
 * Debug mode: the user signs in with any username, and requests carry an unsigned
 * token for it. There is NO real authentication. Only for development against a
 * backend with `AUTH_DISABLED=true`.
 *
 * The username is kept in `localStorage`, so the session survives a reload
 * (like Firebase, which persists its session by default).
 */
export class DebugAuthService implements AuthService {
	readonly mode = 'debug';

	#user = $state<AuthUser | null>(null);
	#signOutReason = $state<SignOutReason | null>(null);
	readonly #storage: () => Storage | null;

	constructor(storage: () => Storage | null = getStorage) {
		this.#storage = storage;
	}

	get user() {
		return this.#user;
	}

	get signOutReason() {
		return this.#signOutReason;
	}

	async init(): Promise<void> {
		try {
			const stored = this.#storage()?.getItem(STORAGE_KEY);
			if (stored && validateDebugUsername(stored) === null) {
				this.#user = { uid: stored, displayName: stored };
			}
		} catch {
			// Storage not accessible: start signed out.
		}
	}

	/** Signs in as `username`. Throws if the username is invalid. */
	async signIn(username: string): Promise<void> {
		const problem = validateDebugUsername(username);
		if (problem) throw new Error(problem);

		const uid = username.trim();
		this.#user = { uid, displayName: uid };
		this.#signOutReason = null;
		try {
			this.#storage()?.setItem(STORAGE_KEY, uid);
		} catch {
			// Not persisted; the session lasts until the page is reloaded.
		}
	}

	async getIdToken(): Promise<string | null> {
		return this.#user ? createDebugToken(this.#user.uid) : null;
	}

	async signOut(reason: SignOutReason = 'user'): Promise<void> {
		this.#user = null;
		this.#signOutReason = reason;
		try {
			this.#storage()?.removeItem(STORAGE_KEY);
		} catch {
			// Nothing to clean up.
		}
	}
}
