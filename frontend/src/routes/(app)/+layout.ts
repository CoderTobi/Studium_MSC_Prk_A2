import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { auth } from '#lib/services.ts';

/** Route guard: everything in `(app)` requires a signed-in user. */
export async function load({ parent }) {
	await parent(); // the root layout restores the session first
	if (!auth.user) redirect(307, resolve('/login'));
}
