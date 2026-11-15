<!--
	Sign-in for the debug mode: any username, no password. Requests are sent with an
	unsigned token for that username, which only a backend with AUTH_DISABLED=true accepts.
-->
<script lang="ts">
	import type { DebugAuthService } from '#lib/auth/index.ts';
	import { validateDebugUsername } from '#lib/auth/debug-token.ts';

	interface Props {
		auth: DebugAuthService;
		onSignedIn: () => void;
	}

	let { auth, onSignedIn }: Props = $props();

	let username = $state('');
	let error = $state<string | null>(null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		error = validateDebugUsername(username);
		if (error) return;
		await auth.signIn(username);
		onSignedIn();
	}
</script>

<form class="space-y-4" onsubmit={submit} novalidate>
	<div class="space-y-1.5">
		<label for="username" class="block text-sm font-medium text-slate-700">Username</label>
		<input
			bind:value={username}
			oninput={() => (error = null)}
			id="username"
			name="username"
			type="text"
			class="input"
			autocomplete="username"
			autocapitalize="none"
			spellcheck="false"
			placeholder="e.g. alice"
			aria-invalid={error ? 'true' : undefined}
			aria-describedby="username-hint{error ? ' username-error' : ''}"
		/>
		<p id="username-hint" class="text-xs text-slate-500">
			Each username has its own shopping list. No password is needed in debug mode.
		</p>
		{#if error}
			<p id="username-error" class="text-sm text-red-700">{error}</p>
		{/if}
	</div>
	<button type="submit" class="btn-primary w-full">Sign in</button>
</form>
