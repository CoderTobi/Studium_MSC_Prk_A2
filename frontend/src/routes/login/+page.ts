import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { auth } from '#lib/services.ts';

/** Already signed in: go straight to the list. */
export async function load({ parent }) {
	await parent();
	if (auth.user) redirect(307, resolve('/(app)'));
}
