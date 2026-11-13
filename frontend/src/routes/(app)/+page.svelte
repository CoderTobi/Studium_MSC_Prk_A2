<script lang="ts">
	import { onMount } from 'svelte';
	import ErrorAlert from '#lib/components/ErrorAlert.svelte';
	import Icon from '#lib/components/icons/Icon.svelte';
	import AddItemForm from '#lib/components/items/AddItemForm.svelte';
	import ItemList from '#lib/components/items/ItemList.svelte';
	import AiDisclaimer from '#lib/components/recommendations/AiDisclaimer.svelte';
	import PromptForm from '#lib/components/recommendations/PromptForm.svelte';
	import SuggestionPanel from '#lib/components/recommendations/SuggestionPanel.svelte';
	import Spinner from '#lib/components/Spinner.svelte';
	import { api } from '#lib/services.ts';
	import { RecommendationsStore } from '#lib/stores/recommendations.svelte.ts';
	import { ShoppingListStore } from '#lib/stores/shopping-list.svelte.ts';

	// Created per page instance, so nothing is left over after a sign-out.
	const list = new ShoppingListStore(api.items);
	const recommendations = new RecommendationsStore(api.recommendations, (names) =>
		list.addMany(names, 'ai_recommendation')
	);

	onMount(() => {
		void list.load();
		return () => recommendations.cancel();
	});
</script>

<svelte:head>
	<title>My shopping list · AI Shopping List</title>
</svelte:head>

<div class="grid items-start gap-6 lg:grid-cols-2">
	<section aria-labelledby="list-heading" class="space-y-4 card">
		<div class="flex items-baseline justify-between gap-2">
			<h1 id="list-heading" class="text-lg font-semibold">My shopping list</h1>
			{#if list.loadState === 'ready'}
				<span class="text-sm text-slate-500">
					{list.items.length}
					{list.items.length === 1 ? 'item' : 'items'}
				</span>
			{/if}
		</div>

		<AddItemForm onAdd={(name) => list.add(name)} busy={list.adding} />

		{#if list.removeError}
			<ErrorAlert error={list.removeError} onDismiss={() => list.dismissRemoveError()} />
		{/if}

		{#if list.loadState === 'loading' || list.loadState === 'idle'}
			<p class="flex items-center gap-2 py-6 text-sm text-slate-500" aria-live="polite">
				<Spinner /> Loading your list…
			</p>
		{:else if list.loadState === 'error' && list.loadError}
			<div class="space-y-3">
				<ErrorAlert error={list.loadError} />
				<button type="button" class="btn-secondary" onclick={() => list.load()}>Try again</button>
			</div>
		{:else if list.items.length === 0}
			<p
				class="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
			>
				Your list is empty. Add an item above or ask the AI for ideas.
			</p>
		{:else}
			<ItemList
				items={list.items}
				isRemoving={(id) => list.isRemoving(id)}
				onRemove={(id) => list.remove(id)}
			/>
		{/if}
	</section>

	<section aria-labelledby="ai-heading" class="space-y-4 card">
		<div class="space-y-1">
			<h2 id="ai-heading" class="flex items-center gap-2 text-lg font-semibold">
				<Icon name="sparkles" class="size-5 text-ai-600" />
				Ask the AI
			</h2>
			<p class="text-sm text-slate-600">
				Describe a dish or meal and get suggestions for your shopping list. You decide which ones to
				add.
			</p>
		</div>

		<PromptForm
			loading={recommendations.state === 'loading'}
			onSubmit={(prompt) => recommendations.request(prompt)}
			onCancel={() => recommendations.cancel()}
		/>

		<div aria-live="polite" class="space-y-4">
			{#if recommendations.requestError}
				<ErrorAlert
					error={recommendations.requestError}
					onDismiss={() => recommendations.dismissRequestError()}
				/>
			{/if}

			{#if recommendations.state === 'ready'}
				<SuggestionPanel store={recommendations} />
			{:else}
				<AiDisclaimer />
			{/if}
		</div>
	</section>
</div>
