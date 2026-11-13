import type { AuthMode } from '#lib/config/parse.ts';
import { DebugAuthService } from './debug.svelte.ts';

export type { AuthService, AuthUser, SignOutReason } from './types';
export { DebugAuthService } from './debug.svelte.ts';

/**
 * All auth implementations. The login page narrows on `mode` to show the matching
 * sign-in form. Add `FirebaseAuthService` here when Firebase is introduced.
 */
export type AppAuthService = DebugAuthService;

export function createAuthService(mode: AuthMode): AppAuthService {
	switch (mode) {
		case 'debug':
			return new DebugAuthService();
		default: {
			const unsupported: never = mode;
			throw new Error(`Unsupported auth mode: ${String(unsupported)}`);
		}
	}
}
