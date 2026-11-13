<!--
	Small inline SVG icon set (no icon library dependency). Paths are 24×24 outline icons.
	Decorative by default; pass `label` to make the icon meaningful to screen readers.
-->
<script lang="ts" module>
	const PATHS = {
		sparkles:
			'M9.8 4.6 11 8l3.4 1.2L11 10.4 9.8 13.8 8.6 10.4 5.2 9.2 8.6 8l1.2-3.4ZM17 13l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2ZM17 3l.5 1.5L19 5l-1.5.5L17 7l-.5-1.5L15 5l1.5-.5L17 3Z',
		trash:
			'M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3',
		close: 'M6 6l12 12M18 6 6 18',
		plus: 'M12 5v14M5 12h14',
		info: 'M12 8h.01M11 12h1v4h1M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z',
		cart: 'M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2M10 21h.01M17 21h.01',
		logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3'
	} as const;

	export type IconName = keyof typeof PATHS;
</script>

<script lang="ts">
	interface Props {
		name: IconName;
		class?: string;
		label?: string;
	}

	let { name, class: className = 'size-5', label }: Props = $props();
</script>

<svg
	class={className}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.75"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden={label ? undefined : 'true'}
	role={label ? 'img' : undefined}
	aria-label={label}
>
	<path d={PATHS[name]} />
</svg>
