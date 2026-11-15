<script lang="ts">
	let { class: className = 'size-4' }: { class?: string } = $props();
</script>

<svg class="animate-spin {className}" viewBox="0 0 24 24" fill="none" aria-hidden="true">
	<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" />
	<path class="opacity-90" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" stroke-width="3" />
</svg>
