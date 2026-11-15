import { describe, expect, it } from 'vitest';
import { firebaseErrorMessage } from './firebase-errors.ts';
import { FirebaseAuthService, type FirebaseSdk, type FirebaseSdkUser } from './firebase.svelte.ts';

function sdkUser(uid: string, email: string | null = `${uid}@example.org`): FirebaseSdkUser {
	return { uid, email, getIdToken: async () => `token-of-${uid}` };
}

/** In-memory replacement for the Firebase JS SDK. */
class FakeSdk implements FirebaseSdk {
	user: FirebaseSdkUser | null;
	listener: ((user: FirebaseSdkUser | null) => void) | null = null;
	calls: string[] = [];
	failWith: unknown = null;

	constructor(user: FirebaseSdkUser | null = null) {
		this.user = user;
	}

	async ready() {}
	currentUser() {
		return this.user;
	}
	onUserChanged(listener: (user: FirebaseSdkUser | null) => void) {
		this.listener = listener;
	}
	async signIn(email: string, password: string) {
		return this.#signIn('signIn', email, password);
	}
	async signUp(email: string, password: string) {
		return this.#signIn('signUp', email, password);
	}
	async signOut() {
		this.calls.push('signOut');
		this.emit(null);
	}

	/** What Firebase does on a sign-in or sign-out, also one from another tab. */
	emit(user: FirebaseSdkUser | null) {
		this.user = user;
		this.listener?.(user);
	}

	#signIn(call: string, email: string, password: string) {
		this.calls.push(`${call}:${email}:${password}`);
		if (this.failWith) throw this.failWith;
		const user = sdkUser('alice', email);
		this.emit(user);
		return user;
	}
}

async function create(user: FirebaseSdkUser | null = null) {
	const sdk = new FakeSdk(user);
	const auth = new FirebaseAuthService(async () => sdk);
	await auth.init();
	return { sdk, auth };
}

describe('FirebaseAuthService', () => {
	it('is signed out and sends no token by default', async () => {
		const { auth } = await create();
		expect(auth.mode).toBe('firebase');
		expect(auth.user).toBeNull();
		expect(auth.signOutReason).toBeNull();
		expect(await auth.getIdToken()).toBeNull();
	});

	it('sends no token before init', async () => {
		const auth = new FirebaseAuthService(async () => new FakeSdk(sdkUser('alice')));
		expect(await auth.getIdToken()).toBeNull();
		await expect(auth.signIn('a@example.org', 'secret1')).rejects.toThrow(/init/);
	});

	it('restores a persisted session', async () => {
		const { auth } = await create(sdkUser('alice'));
		expect(auth.user).toEqual({ uid: 'alice', displayName: 'alice@example.org' });
		expect(await auth.getIdToken()).toBe('token-of-alice');
	});

	it('loads the SDK only once', async () => {
		let loads = 0;
		const auth = new FirebaseAuthService(async () => {
			loads += 1;
			return new FakeSdk();
		});
		await auth.init();
		await auth.init();
		expect(loads).toBe(1);
	});

	it('signs in with the trimmed email and the unchanged password', async () => {
		const { auth, sdk } = await create();
		await auth.signIn(' alice@example.org ', ' secret ');

		expect(sdk.calls).toEqual(['signIn:alice@example.org: secret ']);
		expect(auth.user).toEqual({ uid: 'alice', displayName: 'alice@example.org' });
		expect(await auth.getIdToken()).toBe('token-of-alice');
	});

	it('creates an account and is signed in afterwards', async () => {
		const { auth, sdk } = await create();
		await auth.signUp('alice@example.org', 'secret1');

		expect(sdk.calls).toEqual(['signUp:alice@example.org:secret1']);
		expect(auth.user?.uid).toBe('alice');
	});

	it('passes Firebase errors on and stays signed out', async () => {
		const { auth, sdk } = await create();
		sdk.failWith = { code: 'auth/invalid-credential' };

		await expect(auth.signIn('alice@example.org', 'wrong')).rejects.toBe(sdk.failWith);
		expect(auth.user).toBeNull();
	});

	it('signs out with a reason', async () => {
		const { auth, sdk } = await create(sdkUser('alice'));
		await auth.signOut('session-expired');

		expect(sdk.calls).toEqual(['signOut']);
		expect(auth.user).toBeNull();
		expect(auth.signOutReason).toBe('session-expired');
		expect(await auth.getIdToken()).toBeNull();
	});

	it('clears the sign-out reason on the next sign-in', async () => {
		const { auth } = await create(sdkUser('alice'));
		await auth.signOut();
		expect(auth.signOutReason).toBe('user');

		await auth.signIn('alice@example.org', 'secret1');
		expect(auth.signOutReason).toBeNull();
	});

	it('follows a session that Firebase ends by itself', async () => {
		const { auth, sdk } = await create(sdkUser('alice'));
		sdk.emit(null);

		expect(auth.user).toBeNull();
		expect(auth.signOutReason).toBe('session-expired');
	});

	it('uses the uid as name for a user without email', async () => {
		const { auth } = await create(sdkUser('alice', null));
		expect(auth.user?.displayName).toBe('alice');
	});

	it('sends no token if it cannot be refreshed', async () => {
		const { auth } = await create({
			...sdkUser('alice'),
			getIdToken: async () => {
				throw new Error('network');
			}
		});
		expect(await auth.getIdToken()).toBeNull();
	});
});

describe('firebaseErrorMessage', () => {
	it.each(['auth/invalid-credential', 'auth/wrong-password', 'auth/user-not-found'])(
		'does not reveal whether the account exists (%s)',
		(code) => {
			expect(firebaseErrorMessage({ code })).toBe('Wrong email or password.');
		}
	);

	it.each([
		['auth/email-already-in-use', /already exists/],
		['auth/weak-password', /at least 6 characters/],
		['auth/too-many-requests', /Too many attempts/],
		['auth/network-request-failed', /connection/],
		['auth/invalid-email', /valid email/]
	])('explains %s', (code, message) => {
		expect(firebaseErrorMessage({ code })).toMatch(message);
	});

	it.each([
		[{ code: 'auth/internal-error', message: 'Firebase: Error (auth/internal-error).' }],
		[{ code: 'toString' }],
		[{ code: 42 }],
		[new Error('Firebase: secret detail')],
		['text'],
		[null]
	])('never shows the technical message (%j)', (error) => {
		expect(firebaseErrorMessage(error)).toBe('Something went wrong. Please try again.');
	});
});
