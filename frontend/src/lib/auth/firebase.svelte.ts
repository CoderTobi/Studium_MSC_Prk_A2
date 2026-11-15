import type { AuthService, AuthUser, SignOutReason } from './types';

/** The part of a Firebase user the app uses. */
export interface FirebaseSdkUser {
	uid: string;
	email: string | null;
	/** Returns the cached ID token and refreshes it shortly before it expires. */
	getIdToken(): Promise<string>;
}

/** The part of the Firebase JS SDK the app uses (see `firebase-sdk.ts`). */
export interface FirebaseSdk {
	/** Resolves once a persisted session has been restored. */
	ready(): Promise<void>;
	currentUser(): FirebaseSdkUser | null;
	/** Calls `listener` on every sign-in and sign-out, also from another tab. */
	onUserChanged(listener: (user: FirebaseSdkUser | null) => void): void;
	signIn(email: string, password: string): Promise<FirebaseSdkUser>;
	signUp(email: string, password: string): Promise<FirebaseSdkUser>;
	signOut(): Promise<void>;
}

function toAuthUser(user: FirebaseSdkUser | null): AuthUser | null {
	return user ? { uid: user.uid, displayName: user.email ?? user.uid } : null;
}

/**
 * Firebase Authentication with email and password.
 *
 * Firebase keeps the session in the browser and refreshes the ID token (valid for one
 * hour) by itself. The backend verifies that token on every request.
 */
export class FirebaseAuthService implements AuthService {
	readonly mode = 'firebase';

	#user = $state<AuthUser | null>(null);
	#signOutReason = $state<SignOutReason | null>(null);
	#sdk: FirebaseSdk | null = null;
	readonly #loadSdk: () => Promise<FirebaseSdk>;

	constructor(loadSdk: () => Promise<FirebaseSdk>) {
		this.#loadSdk = loadSdk;
	}

	get user() {
		return this.#user;
	}

	get signOutReason() {
		return this.#signOutReason;
	}

	async init(): Promise<void> {
		if (this.#sdk) return;
		const sdk = await this.#loadSdk();
		await sdk.ready();
		this.#sdk = sdk;
		this.#user = toAuthUser(sdk.currentUser());
		sdk.onUserChanged((user) => this.#setUser(user));
	}

	/** Signs in. Rejects with the Firebase error, see `firebaseErrorMessage`. */
	async signIn(email: string, password: string): Promise<void> {
		this.#setUser(await this.#requireSdk().signIn(email.trim(), password));
	}

	/** Creates an account and signs in. Rejects with the Firebase error. */
	async signUp(email: string, password: string): Promise<void> {
		this.#setUser(await this.#requireSdk().signUp(email.trim(), password));
	}

	async getIdToken(): Promise<string | null> {
		try {
			return (await this.#sdk?.currentUser()?.getIdToken()) ?? null;
		} catch {
			// The token could not be refreshed. Without a token the backend answers 401,
			// which ends the session (see `services.ts`).
			return null;
		}
	}

	async signOut(reason: SignOutReason = 'user'): Promise<void> {
		this.#user = null;
		this.#signOutReason = reason;
		await this.#sdk?.signOut();
	}

	#setUser(sdkUser: FirebaseSdkUser | null): void {
		const user = toAuthUser(sdkUser);
		if (user) {
			this.#signOutReason = null;
		} else if (this.#user) {
			// Not signed out through `signOut()`: Firebase ended the session, for example
			// because the account was deleted or the user signed out in another tab.
			this.#signOutReason = 'session-expired';
		}
		if (user?.uid !== this.#user?.uid || user?.displayName !== this.#user?.displayName) {
			this.#user = user;
		}
	}

	#requireSdk(): FirebaseSdk {
		if (!this.#sdk) throw new Error('FirebaseAuthService.init() has not finished');
		return this.#sdk;
	}
}
