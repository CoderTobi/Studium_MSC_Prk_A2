<!--
	Sign-in and account creation with Firebase Authentication (email and password).
	A new account is signed in right away.
-->
<script lang="ts">
	import type { FirebaseAuthService } from '#lib/auth/index.ts';
	import { PASSWORD_MIN_LENGTH, firebaseErrorMessage } from '#lib/auth/firebase-errors.ts';
	import Spinner from '../Spinner.svelte';

	interface Props {
		auth: FirebaseAuthService;
		onSignedIn: () => void;
	}

	let { auth, onSignedIn }: Props = $props();

	let creating = $state(false);
	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	function validate(): string | null {
		if (!email.trim()) return 'Please enter your email address.';
		if (!password) return 'Please enter your password.';
		if (creating && password.length < PASSWORD_MIN_LENGTH) {
			return `The password must have at least ${PASSWORD_MIN_LENGTH} characters.`;
		}
		return null;
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		error = validate();
		if (error) return;

		busy = true;
		try {
			if (creating) await auth.signUp(email, password);
			else await auth.signIn(email, password);
		} catch (cause) {
			error = firebaseErrorMessage(cause);
			return;
		} finally {
			busy = false;
		}
		onSignedIn();
	}

	function toggleMode() {
		creating = !creating;
		error = null;
	}
</script>

<form class="space-y-4" onsubmit={submit} novalidate>
	<div class="space-y-1.5">
		<label for="email" class="block text-sm font-medium text-slate-700">Email</label>
		<input
			bind:value={email}
			oninput={() => (error = null)}
			id="email"
			name="email"
			type="email"
			class="input"
			autocomplete="email"
			autocapitalize="none"
			spellcheck="false"
			aria-invalid={error ? 'true' : undefined}
			aria-describedby={error ? 'sign-in-error' : undefined}
		/>
	</div>
	<div class="space-y-1.5">
		<label for="password" class="block text-sm font-medium text-slate-700">Password</label>
		<input
			bind:value={password}
			oninput={() => (error = null)}
			id="password"
			name="password"
			type="password"
			class="input"
			autocomplete={creating ? 'new-password' : 'current-password'}
			aria-invalid={error ? 'true' : undefined}
			aria-describedby="{creating ? 'password-hint' : ''}{error ? ' sign-in-error' : ''}"
		/>
		{#if creating}
			<p id="password-hint" class="text-xs text-slate-500">
				At least {PASSWORD_MIN_LENGTH} characters.
			</p>
		{/if}
	</div>

	{#if error}
		<p id="sign-in-error" role="alert" class="text-sm text-red-700">{error}</p>
	{/if}

	<button type="submit" class="btn-primary w-full" disabled={busy}>
		{#if busy}<Spinner />{/if}
		{creating ? 'Create account' : 'Sign in'}
	</button>

	<p class="text-center text-sm text-slate-600">
		{creating ? 'Already have an account?' : 'No account yet?'}
		<button type="button" class="link" onclick={toggleMode} disabled={busy}>
			{creating ? 'Sign in' : 'Create account'}
		</button>
	</p>
</form>
