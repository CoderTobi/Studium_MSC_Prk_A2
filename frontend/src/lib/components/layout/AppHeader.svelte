<script lang="ts">
	import { resolve } from '$app/paths';
	import type { AuthUser } from '#lib/auth/index.ts';
	import Icon from '../icons/Icon.svelte';

	interface Props {
		user: AuthUser | null;
		onSignOut: () => void;
	}

	let { user, onSignOut }: Props = $props();
</script>

<header class="border-b border-slate-200 bg-white">
	<div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
		<a
			href={resolve('/(app)')}
			class="flex items-center gap-2 rounded font-semibold text-slate-900 focus-visible:outline-2 focus-visible:outline-brand-600"
		>
			<span class="grid size-8 place-items-center rounded-lg bg-brand-600 text-white">
				<Icon name="cart" class="size-5" />
			</span>
			AI Shopping List
		</a>

		{#if user}
			<div class="flex min-w-0 items-center gap-3">
				<span class="hidden truncate text-sm text-slate-600 sm:inline">
					Signed in as <span class="font-medium text-slate-900">{user.displayName}</span>
				</span>
				<button type="button" class="btn-secondary" onclick={onSignOut}>
					<Icon name="logout" class="size-4" />
					Sign out
				</button>
			</div>
		{/if}
	</div>
</header>
