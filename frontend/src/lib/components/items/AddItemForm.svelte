<script lang="ts">
	import type { ApiError } from '#lib/api/index.ts';
	import { ITEM_NAME_MAX_LENGTH, validateItemName } from '#lib/api/limits.ts';
	import ErrorAlert from '../ErrorAlert.svelte';
	import Icon from '../icons/Icon.svelte';

	interface Props {
		/** Adds the item. Resolves to `null` on success, otherwise to the error. */
		onAdd: (name: string) => Promise<ApiError | null>;
		busy?: boolean;
	}

	let { onAdd, busy = false }: Props = $props();

	let name = $state('');
	let validationError = $state<string | null>(null);
	let apiError = $state<ApiError | null>(null);
	let input: HTMLInputElement;

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		validationError = validateItemName(name);
		apiError = null;
		if (validationError) {
			input.focus();
			return;
		}

		const error = await onAdd(name);
		if (error) {
			apiError = error;
			return;
		}
		name = '';
		input.focus();
	}
</script>

<form class="space-y-2" onsubmit={submit} novalidate>
	<label for="new-item" class="sr-only">New item</label>
	<div class="flex gap-2">
		<input
			bind:this={input}
			bind:value={name}
			oninput={() => (validationError = null)}
			id="new-item"
			name="name"
			type="text"
			class="input"
			placeholder="Add an item, e.g. Milk"
			autocomplete="off"
			enterkeyhint="done"
			maxlength={ITEM_NAME_MAX_LENGTH * 2}
			aria-invalid={validationError ? 'true' : undefined}
			aria-describedby={validationError ? 'new-item-error' : undefined}
		/>
		<button type="submit" class="btn-primary" disabled={busy}>
			<Icon name="plus" class="size-4" />
			Add
		</button>
	</div>
	{#if validationError}
		<p id="new-item-error" class="text-sm text-red-700">{validationError}</p>
	{/if}
	{#if apiError}
		<ErrorAlert error={apiError} onDismiss={() => (apiError = null)} />
	{/if}
</form>
