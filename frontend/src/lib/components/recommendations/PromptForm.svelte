<script lang="ts">
	import { PROMPT_MAX_LENGTH, textLength, validatePrompt } from '#lib/api/limits.ts';
	import Icon from '../icons/Icon.svelte';
	import Spinner from '../Spinner.svelte';

	interface Props {
		loading: boolean;
		onSubmit: (prompt: string) => void;
		onCancel: () => void;
	}

	let { loading, onSubmit, onCancel }: Props = $props();

	let prompt = $state('');
	let validationError = $state<string | null>(null);
	const length = $derived(textLength(prompt.trim()));
	const tooLong = $derived(length > PROMPT_MAX_LENGTH);

	function submit(event?: SubmitEvent) {
		event?.preventDefault();
		if (loading) return;
		validationError = validatePrompt(prompt);
		if (!validationError) onSubmit(prompt);
	}

	function onkeydown(event: KeyboardEvent) {
		// Ctrl/Cmd + Enter submits, plain Enter adds a new line.
		if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
			event.preventDefault();
			submit();
		}
	}
</script>

<form class="space-y-2" onsubmit={submit} novalidate>
	<label for="prompt" class="block text-sm font-medium text-slate-700">
		What would you like to eat?
	</label>
	<textarea
		bind:value={prompt}
		oninput={() => (validationError = null)}
		{onkeydown}
		id="prompt"
		name="prompt"
		rows="3"
		class="input resize-y focus:border-ai-600 focus:ring-ai-600/20"
		placeholder="e.g. Spaghetti bolognese for four people tonight"
		aria-invalid={validationError || tooLong ? 'true' : undefined}
		aria-describedby="prompt-hint{validationError ? ' prompt-error' : ''}"></textarea>

	<div class="flex items-center justify-between gap-2 text-xs text-slate-500">
		<span id="prompt-hint" class="hidden sm:inline">Ctrl + Enter to send</span>
		<span class="ml-auto tabular-nums" class:text-red-700={tooLong}>
			{length} / {PROMPT_MAX_LENGTH}
		</span>
	</div>

	{#if validationError}
		<p id="prompt-error" class="text-sm text-red-700">{validationError}</p>
	{/if}

	<div class="flex flex-wrap gap-2">
		<button type="submit" class="btn-ai" disabled={loading}>
			{#if loading}
				<Spinner />
				Thinking…
			{:else}
				<Icon name="sparkles" class="size-4" />
				Get suggestions
			{/if}
		</button>
		{#if loading}
			<button type="button" class="btn-secondary" onclick={onCancel}>Cancel</button>
		{/if}
	</div>
</form>
