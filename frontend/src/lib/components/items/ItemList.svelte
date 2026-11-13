<script lang="ts">
	import type { Item } from '#lib/api/index.ts';
	import AiBadge from '../AiBadge.svelte';
	import Icon from '../icons/Icon.svelte';
	import Spinner from '../Spinner.svelte';

	interface Props {
		items: readonly Item[];
		isRemoving: (id: string) => boolean;
		onRemove: (id: string) => void;
	}

	let { items, isRemoving, onRemove }: Props = $props();
</script>

<ul class="divide-y divide-slate-100" aria-label="Items">
	{#each items as item (item.id)}
		{@const removing = isRemoving(item.id)}
		<li class="flex items-center gap-3 py-2.5" class:opacity-50={removing}>
			<!-- Always rendered as text, never as HTML. -->
			<span class="min-w-0 flex-1 break-words">{item.name}</span>
			{#if item.source === 'ai_recommendation'}
				<AiBadge />
			{/if}
			<button
				type="button"
				class="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 focus-visible:outline-2 focus-visible:outline-red-600 disabled:cursor-not-allowed"
				disabled={removing}
				onclick={() => onRemove(item.id)}
			>
				{#if removing}
					<Spinner />
					<span class="sr-only">Removing {item.name}</span>
				{:else}
					<Icon name="trash" class="size-4" label="Remove {item.name}" />
				{/if}
			</button>
		</li>
	{/each}
</ul>
