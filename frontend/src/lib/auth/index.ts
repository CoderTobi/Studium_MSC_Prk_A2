import type { AuthMode } from '#lib/config/parse.ts';
import { DebugAuthService } from './debug.svelte.ts';
import { FirebaseAuthService } from './firebase.svelte.ts';

export type { AuthService, AuthUser, SignOutReason } from './types';
export { DebugAuthService } from './debug.svelte.ts';
export { FirebaseAuthService } from './firebase.svelte.ts';

/**
 * All auth implementations. The login page narrows on `mode` to show the matching
 * sign-in form.
 */
export type AppAuthService = FirebaseAuthService | DebugAuthService;

export interface AuthConfig {
	authMode: AuthMode;
	/** Required for the `firebase` mode. */
	firebaseApiKey: string | null;
}

export function createAuthService({ authMode, firebaseApiKey }: AuthConfig): AppAuthService {
	switch (authMode) {
		case 'firebase': {
			if (!firebaseApiKey) throw new Error('The firebase auth mode needs an API key');
			// Loaded on demand, so the debug mode never downloads the Firebase SDK.
			return new FirebaseAuthService(async () => {
				const { createFirebaseSdk } = await import('./firebase-sdk.ts');
				return createFirebaseSdk(firebaseApiKey);
			});
		}
		case 'debug':
			return new DebugAuthService();
		default: {
			const unsupported: never = authMode;
			throw new Error(`Unsupported auth mode: ${String(unsupported)}`);
		}
	}
}
