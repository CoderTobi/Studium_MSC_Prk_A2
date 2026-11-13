import { json } from '@sveltejs/kit';

/** Liveness check for the container healthcheck. Says nothing about the backend. */
export function GET() {
	return json({ status: 'ok' }, { headers: { 'Cache-Control': 'no-store' } });
}
