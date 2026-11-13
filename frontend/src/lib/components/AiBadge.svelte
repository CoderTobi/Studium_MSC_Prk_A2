<!-- Marks content as AI generated. Used on suggestions and on accepted AI items. -->
<script lang="ts">
	import Icon from './icons/Icon.svelte';

	let { label = 'AI' }: { label?: string } = $props();
</script>

<span
	class="inline-flex shrink-0 items-center gap-1 rounded-full bg-ai-100 px-2 py-0.5 text-xs font-medium text-ai-800 ring-1 ring-ai-200 ring-inset"
	title="Suggested by AI"
>
	<Icon name="sparkles" class="size-3.5" />
	{label}
</span>
