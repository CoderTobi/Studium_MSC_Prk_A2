import { describe, expect, it } from 'vitest';
import { createDebugToken, validateDebugUsername } from './debug-token.ts';
import { DebugAuthService } from './debug.svelte.ts';

function decodePart(part: string): unknown {
	const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
	return JSON.parse(Buffer.from(base64, 'base64').toString('utf8'));
}

class MemoryStorage implements Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> {
	values = new Map<string, string>();
	getItem(key: string) {
		return this.values.get(key) ?? null;
	}
	setItem(key: string, value: string) {
		this.values.set(key, value);
	}
	removeItem(key: string) {
		this.values.delete(key);
	}
}

describe('createDebugToken', () => {
	it('creates an unsigned JWT with the uid as sub claim', () => {
		const token = createDebugToken('alice');
		const [header, payload, signature] = token.split('.');

		expect(token.split('.')).toHaveLength(3);
		expect(decodePart(header)).toEqual({ alg: 'none', typ: 'JWT' });
		expect(decodePart(payload)).toEqual({ sub: 'alice' });
		expect(signature).toBe('');
		expect(token).not.toMatch(/[+/=]/);
	});
});

describe('validateDebugUsername', () => {
	it.each(['alice', 'Bob_2', 'debug-user'])('accepts %s', (name) => {
		expect(validateDebugUsername(name)).toBeNull();
	});

	it.each(['', '  ', 'a/b', '..', 'with space', 'x'.repeat(65), '__name__!'])(
		'rejects %j',
		(name) => {
			expect(validateDebugUsername(name)).not.toBeNull();
		}
	);
});

describe('DebugAuthService', () => {
	function create() {
		const storage = new MemoryStorage();
		return { storage, auth: new DebugAuthService(() => storage as unknown as Storage) };
	}

	it('is signed out and sends no token by default', async () => {
		const { auth } = create();
		await auth.init();
		expect(auth.user).toBeNull();
		expect(await auth.getIdToken()).toBeNull();
	});

	it('signs in, persists the session and restores it', async () => {
		const { auth, storage } = create();
		await auth.signIn('  alice ');

		expect(auth.user).toEqual({ uid: 'alice', displayName: 'alice' });
		expect(await auth.getIdToken()).toBe(createDebugToken('alice'));

		const restored = new DebugAuthService(() => storage as unknown as Storage);
		await restored.init();
		expect(restored.user?.uid).toBe('alice');
	});

	it('rejects invalid usernames', async () => {
		const { auth } = create();
		await expect(auth.signIn('a/b')).rejects.toThrow();
		expect(auth.user).toBeNull();
	});

	it('ignores an invalid stored username', async () => {
		const { auth, storage } = create();
		storage.setItem('shopping-list.debug-username', '../other');
		await auth.init();
		expect(auth.user).toBeNull();
	});

	it('signs out with a reason and clears the session', async () => {
		const { auth, storage } = create();
		await auth.signIn('alice');
		await auth.signOut('session-expired');

		expect(auth.user).toBeNull();
		expect(auth.signOutReason).toBe('session-expired');
		expect(storage.values.size).toBe(0);
		expect(await auth.getIdToken()).toBeNull();
	});

	it('works without storage', async () => {
		const auth = new DebugAuthService(() => null);
		await auth.init();
		await auth.signIn('alice');
		expect(auth.user?.uid).toBe('alice');
	});
});
