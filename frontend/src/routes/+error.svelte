<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
</script>

<svelte:head>
	<title>{page.status} · AI Shopping List</title>
</svelte:head>

<div class="mx-auto max-w-md space-y-4 py-10 text-center">
	<p class="text-5xl font-bold text-slate-300">{page.status}</p>
	<h1 class="text-xl font-semibold">
		{page.status === 404 ? 'Page not found' : 'Something went wrong'}
	</h1>
	<p class="text-sm text-slate-600">
		{page.status === 404
			? 'The page you are looking for does not exist.'
			: 'Please try again later.'}
	</p>
	<a href={resolve('/(app)')} class="btn-primary">Back to my list</a>
</div>
