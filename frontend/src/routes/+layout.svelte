<script lang="ts">
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import AppFooter from '#lib/components/layout/AppFooter.svelte';
	import AppHeader from '#lib/components/layout/AppHeader.svelte';
	import DebugModeBanner from '#lib/components/layout/DebugModeBanner.svelte';
	import { auth } from '#lib/services.ts';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// Protected pages redirect to the login page by themselves (see `(app)/+layout.svelte`).
	const signOut = () => void auth.signOut();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>AI Shopping List</title>
</svelte:head>

<div class="flex min-h-dvh flex-col">
	{#if auth.mode === 'debug'}
		<DebugModeBanner />
	{/if}
	<AppHeader user={auth.user} onSignOut={signOut} />
	<main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:py-8">
		{@render children()}
	</main>
	<AppFooter />
</div>
