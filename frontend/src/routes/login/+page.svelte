<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import DebugSignInForm from '#lib/components/auth/DebugSignInForm.svelte';
	import { auth } from '#lib/services.ts';

	const onSignedIn = () => void goto(resolve('/(app)'), { replaceState: true });
</script>

<svelte:head>
	<title>Sign in · AI Shopping List</title>
</svelte:head>

<div class="mx-auto max-w-sm space-y-6 py-4 sm:py-10">
	<div class="space-y-1 text-center">
		<h1 class="text-2xl font-semibold">Sign in</h1>
		<p class="text-sm text-slate-600">Sign in to see and edit your shopping list.</p>
	</div>

	{#if auth.signOutReason === 'session-expired'}
		<p
			role="status"
			class="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
		>
			Your session has expired. Please sign in again.
		</p>
	{/if}

	<div class="card">
		<!-- One sign-in form per auth mode. Add the Firebase form here. -->
		{#if auth.mode === 'debug'}
			<DebugSignInForm {auth} {onSignedIn} />
		{/if}
	</div>
</div>
