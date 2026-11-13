<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { auth } from '#lib/services.ts';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// The load function guards navigation. This also covers a sign-out while a page is
	// open, for example after the backend rejected an expired token.
	$effect(() => {
		if (!auth.user) void goto(resolve('/login'), { replaceState: true });
	});
</script>

{#if auth.user}
	{@render children()}
{/if}
