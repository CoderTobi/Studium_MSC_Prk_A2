<!--
	Shows an `ApiError`: the user-safe message, a retry hint for rate limits, invalid
	fields, and the request ID that ties the error to the backend logs.
-->
<script lang="ts">
	import type { ApiError } from '#lib/api/index.ts';
	import Icon from './icons/Icon.svelte';

	interface Props {
		error: ApiError;
		onDismiss?: () => void;
	}

	let { error, onDismiss }: Props = $props();
</script>

<div
	role="alert"
	class="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
>
	<div class="min-w-0 flex-1 space-y-1">
		<p>{error.message}</p>
		{#if error.code === 'RATE_LIMIT_EXCEEDED' && error.retryAfterSeconds !== undefined}
			<p>You can try again in {error.retryAfterSeconds} seconds.</p>
		{/if}
		{#if error.details?.length}
			<ul class="list-inside list-disc">
				{#each error.details as detail (detail.field)}
					<li>{detail.field}: {detail.issue}</li>
				{/each}
			</ul>
		{/if}
		{#if error.requestId}
			<p class="text-xs text-red-700/80">
				Request ID: <span class="font-mono break-all select-all">{error.requestId}</span>
			</p>
		{/if}
	</div>
	{#if onDismiss}
		<button
			type="button"
			class="-m-1 rounded p-1 text-red-700 hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-red-600"
			onclick={onDismiss}
		>
			<Icon name="close" class="size-4" label="Dismiss" />
		</button>
	{/if}
</div>
