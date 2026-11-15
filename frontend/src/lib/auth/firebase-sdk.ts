/**
 * The only file that imports the Firebase JS SDK. It wraps the few functions the app
 * needs in the small `FirebaseSdk` interface, so `FirebaseAuthService` can be tested
 * without Firebase.
 */
import { initializeApp } from 'firebase/app';
import {
	browserLocalPersistence,
	createUserWithEmailAndPassword,
	indexedDBLocalPersistence,
	initializeAuth,
	onAuthStateChanged,
	signInWithEmailAndPassword,
	signOut
} from 'firebase/auth';
import type { FirebaseSdk } from './firebase.svelte.ts';

export function createFirebaseSdk(apiKey: string): FirebaseSdk {
	// Email and password sign-in needs no other value of the Firebase web config.
	const app = initializeApp({ apiKey });
	// `initializeAuth` instead of `getAuth`: without the popup and redirect code, which
	// the app does not use. The session is kept in the browser until the user signs out.
	const auth = initializeAuth(app, {
		persistence: [indexedDBLocalPersistence, browserLocalPersistence]
	});

	return {
		ready: () => auth.authStateReady(),
		currentUser: () => auth.currentUser,
		onUserChanged: (listener) => void onAuthStateChanged(auth, listener),
		signIn: async (email, password) =>
			(await signInWithEmailAndPassword(auth, email, password)).user,
		signUp: async (email, password) =>
			(await createUserWithEmailAndPassword(auth, email, password)).user,
		signOut: () => signOut(auth)
	};
}
