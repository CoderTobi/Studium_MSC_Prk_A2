<!--
	AI suggestions. Visually separated from the shopping list (violet, dashed border,
	"AI suggestions" label) so they are always recognizable as AI generated.
-->
<script lang="ts">
	import type { RecommendationsStore } from '#lib/stores/recommendations.svelte.ts';
	import AiBadge from '../AiBadge.svelte';
	import ErrorAlert from '../ErrorAlert.svelte';
	import Icon from '../icons/Icon.svelte';
	import Spinner from '../Spinner.svelte';
	import AiDisclaimer from './AiDisclaimer.svelte';

	let { store }: { store: RecommendationsStore } = $props();

	const total = $derived(store.suggestions.length);
	const allSelected = $derived(total > 0 && store.selectedCount === total);
</script>

<section
	aria-labelledby="suggestions-heading"
	class="space-y-3 rounded-xl border-2 border-dashed border-ai-300 bg-ai-50 p-4"
>
	<div class="flex flex-wrap items-center justify-between gap-2">
		<h3 id="suggestions-heading" class="flex items-center gap-2 font-semibold text-ai-900">
			AI suggestions <AiBadge label="AI generated" />
		</h3>
		{#if total > 1}
			<button
				type="button"
				class="link text-sm text-ai-700"
				onclick={() => store.selectAll(!allSelected)}
			>
				{allSelected ? 'Select none' : 'Select all'}
			</button>
		{/if}
	</div>

	{#if total === 0}
		<p class="text-sm text-slate-700">
			The AI found no matching items. Try describing a dish or a meal.
		</p>
	{:else}
		<ul class="divide-y divide-ai-100 rounded-lg bg-white ring-1 ring-ai-200">
			{#each store.suggestions as suggestion (suggestion.key)}
				<li class="flex items-center gap-3 px-3 py-2">
					<label class="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
						<input
							type="checkbox"
							class="size-4 shrink-0 accent-ai-600"
							checked={suggestion.selected}
							onchange={() => store.toggle(suggestion.key)}
						/>
						<!-- Always rendered as text, never as HTML. -->
						<span class="min-w-0 break-words">{suggestion.name}</span>
					</label>
					<button
						type="button"
						class="rounded-lg p-1.5 text-ai-700 hover:bg-ai-100 focus-visible:outline-2 focus-visible:outline-ai-600 disabled:opacity-50"
						disabled={store.accepting}
						onclick={() => store.acceptOne(suggestion.key)}
					>
						<Icon name="plus" class="size-4" label="Add {suggestion.name} to the list" />
					</button>
				</li>
			{/each}
		</ul>
	{/if}

	{#if store.acceptError}
		<ErrorAlert error={store.acceptError} onDismiss={() => store.dismissAcceptError()} />
	{/if}

	<div class="flex flex-wrap gap-2">
		{#if total > 0}
			<button
				type="button"
				class="btn-ai"
				disabled={store.accepting || store.selectedCount === 0}
				onclick={() => store.acceptSelected()}
			>
				{#if store.accepting}<Spinner />{:else}<Icon name="plus" class="size-4" />{/if}
				Add selected ({store.selectedCount})
			</button>
		{/if}
		<button
			type="button"
			class="btn-secondary"
			disabled={store.accepting}
			onclick={() => store.discard()}
		>
			{total > 0 ? 'Discard all' : 'Close'}
		</button>
	</div>

	<AiDisclaimer text={store.disclaimer} />
</section>
