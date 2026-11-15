import { describe, expect, it, vi } from 'vitest';
import { ApiClient, type ApiClientOptions } from './client.ts';
import { ApiError } from './errors.ts';
import { createApi } from './index.ts';

const BASE_URL = 'http://backend.test/api/v1';
const REQUEST_ID = '7c1e2f9a-3b4d-4e5f-8a6b-1c2d3e4f5a6b';

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json', 'X-Request-ID': REQUEST_ID, ...headers }
	});
}

function errorBody(code: string, message = 'Safe message', extra: object = {}) {
	return { error: { code, message, requestId: REQUEST_ID, ...extra } };
}

function setup(fetchImpl: typeof fetch, options: Partial<ApiClientOptions> = {}) {
	const fetchMock = vi.fn(fetchImpl);
	const onUnauthenticated = vi.fn();
	const client = new ApiClient({
		baseUrl: BASE_URL,
		getToken: async () => 'token-123',
		onUnauthenticated,
		fetch: fetchMock,
		...options
	});
	return { client, fetchMock, onUnauthenticated };
}

/** A fetch that never answers, but rejects like the real one when its signal aborts. */
const hangingFetch: typeof fetch = (_input, init) =>
	new Promise((_resolve, reject) => {
		const signal = init?.signal;
		if (signal?.aborted) reject(signal.reason);
		signal?.addEventListener('abort', () => reject(signal.reason));
	});

async function catchError(promise: Promise<unknown>): Promise<ApiError> {
	try {
		await promise;
	} catch (error) {
		expect(error).toBeInstanceOf(ApiError);
		return error as ApiError;
	}
	throw new Error('Expected the promise to reject');
}

describe('ApiClient requests', () => {
	it('sends the bearer token, JSON body and headers', async () => {
		const { client, fetchMock } = setup(async () => json(201, { ok: true }));

		await client.request('POST', '/items', { body: { name: 'Milk' } });

		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe(`${BASE_URL}/items`);
		expect(init?.method).toBe('POST');
		expect(init?.body).toBe('{"name":"Milk"}');
		expect(init?.credentials).toBe('omit');
		const headers = new Headers(init?.headers);
		expect(headers.get('Authorization')).toBe('Bearer token-123');
		expect(headers.get('Content-Type')).toBe('application/json');
		expect(headers.get('Accept')).toBe('application/json');
	});

	it('omits the Authorization header without a token and Content-Type without a body', async () => {
		const { client, fetchMock } = setup(async () => json(200, {}), {
			getToken: async () => null
		});

		await client.request('GET', '/items');

		const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
		expect(headers.has('Authorization')).toBe(false);
		expect(headers.has('Content-Type')).toBe(false);
	});

	it('returns the parsed body, and undefined for 204', async () => {
		const { client } = setup(async () => json(200, { items: [] }));
		await expect(client.request('GET', '/items')).resolves.toEqual({ items: [] });

		const { client: client204 } = setup(async () => new Response(null, { status: 204 }));
		await expect(client204.request('DELETE', '/items/a')).resolves.toBeUndefined();
	});
});

describe('ApiClient errors', () => {
	it('parses the ErrorResponse format', async () => {
		const { client } = setup(async () =>
			json(
				400,
				errorBody('VALIDATION_ERROR', 'The request contains invalid fields.', {
					details: [{ field: 'name', issue: 'must not be empty' }, { bogus: true }]
				})
			)
		);

		const error = await catchError(client.request('POST', '/items', { body: {} }));

		expect(error.code).toBe('VALIDATION_ERROR');
		expect(error.status).toBe(400);
		expect(error.message).toBe('The request contains invalid fields.');
		expect(error.requestId).toBe(REQUEST_ID);
		expect(error.details).toEqual([{ field: 'name', issue: 'must not be empty' }]);
	});

	it('reads retryAfterSeconds from the body or the Retry-After header', async () => {
		const fromBody = setup(async () =>
			json(429, errorBody('RATE_LIMIT_EXCEEDED', 'Too many', { retryAfterSeconds: 42 }))
		);
		expect((await catchError(fromBody.client.request('GET', '/items'))).retryAfterSeconds).toBe(42);

		const fromHeader = setup(async () =>
			json(429, errorBody('RATE_LIMIT_EXCEEDED'), { 'Retry-After': '7' })
		);
		const error = await catchError(fromHeader.client.request('GET', '/items'));
		expect(error.code).toBe('RATE_LIMIT_EXCEEDED');
		expect(error.retryAfterSeconds).toBe(7);
	});

	it('calls onUnauthenticated on 401', async () => {
		const { client, onUnauthenticated } = setup(async () =>
			json(401, errorBody('UNAUTHENTICATED'))
		);

		const error = await catchError(client.request('GET', '/items'));

		expect(error.code).toBe('UNAUTHENTICATED');
		expect(onUnauthenticated).toHaveBeenCalledOnce();
	});

	it('does not call onUnauthenticated for other errors', async () => {
		const { client, onUnauthenticated } = setup(async () => json(404, errorBody('ITEM_NOT_FOUND')));
		expect((await catchError(client.request('DELETE', '/items/x'))).code).toBe('ITEM_NOT_FOUND');
		expect(onUnauthenticated).not.toHaveBeenCalled();
	});

	it('maps error responses that are not JSON by status', async () => {
		const html = (status: number) => async () =>
			new Response('<h1>Bad Gateway</h1>', { status, headers: { 'Content-Type': 'text/html' } });

		const proxy = setup(html(502));
		expect(await catchError(proxy.client.request('GET', '/items'))).toMatchObject({
			code: 'INVALID_RESPONSE',
			status: 502
		});

		const unauthenticated = setup(html(401));
		expect((await catchError(unauthenticated.client.request('GET', '/items'))).code).toBe(
			'UNAUTHENTICATED'
		);
		expect(unauthenticated.onUnauthenticated).toHaveBeenCalledOnce();
	});

	it('maps unknown error codes to INVALID_RESPONSE', async () => {
		const { client } = setup(async () => json(500, errorBody('SOMETHING_NEW')));
		expect((await catchError(client.request('GET', '/items'))).code).toBe('INVALID_RESPONSE');
	});

	it('rejects a successful response that is not JSON', async () => {
		const { client } = setup(
			async () => new Response('hello', { status: 200, headers: { 'Content-Type': 'text/plain' } })
		);
		expect((await catchError(client.request('GET', '/items'))).code).toBe('INVALID_RESPONSE');
	});

	it('rejects malformed JSON', async () => {
		const { client } = setup(
			async () =>
				new Response('{"items": [', {
					status: 200,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		expect((await catchError(client.request('GET', '/items'))).code).toBe('INVALID_RESPONSE');
	});

	it('maps network failures to NETWORK_ERROR', async () => {
		const { client } = setup(async () => {
			throw new TypeError('Failed to fetch');
		});
		expect(await catchError(client.request('GET', '/items'))).toMatchObject({
			code: 'NETWORK_ERROR',
			status: 0
		});
	});

	it('maps a timeout to CLIENT_TIMEOUT', async () => {
		const { client } = setup(hangingFetch);
		expect((await catchError(client.request('GET', '/items', { timeoutMs: 10 }))).code).toBe(
			'CLIENT_TIMEOUT'
		);
	});

	it('rethrows the AbortError when the caller cancels', async () => {
		const { client } = setup(hangingFetch);
		const controller = new AbortController();
		const request = client.request('GET', '/items', { signal: controller.signal });
		controller.abort();

		await expect(request).rejects.toMatchObject({ name: 'AbortError' });
	});
});

describe('endpoint functions', () => {
	it('lists items and checks the response shape', async () => {
		const items = [{ id: 'a1', name: 'Milk', source: 'manual' }];
		const api = createApi({
			baseUrl: BASE_URL,
			getToken: async () => null,
			fetch: async () => json(200, { items })
		});
		await expect(api.items.list()).resolves.toEqual(items);

		const broken = createApi({
			baseUrl: BASE_URL,
			getToken: async () => null,
			fetch: async () => json(200, { items: [{ id: 1, name: 'Milk' }] })
		});
		await expect(broken.items.list()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
	});

	it('encodes the item ID in the path', async () => {
		const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
		const api = createApi({ baseUrl: BASE_URL, getToken: async () => null, fetch: fetchMock });

		await api.items.remove('a/b?c');

		expect(fetchMock.mock.calls[0]).toContain(`${BASE_URL}/items/a%2Fb%3Fc`);
	});

	it('sends batches as { items }', async () => {
		const fetchMock = vi.fn(async () =>
			json(201, { items: [{ id: 'x', name: 'Tomatoes', source: 'ai_recommendation' }] })
		);
		const api = createApi({ baseUrl: BASE_URL, getToken: async () => null, fetch: fetchMock });

		await api.items.createMany([{ name: 'Tomatoes', source: 'ai_recommendation' }]);

		const init = (fetchMock.mock.calls[0] as unknown[])[1] as RequestInit;
		expect(JSON.parse(init.body as string)).toEqual({
			items: [{ name: 'Tomatoes', source: 'ai_recommendation' }]
		});
	});

	it('validates recommendation responses', async () => {
		const body = { recommendations: [{ name: 'Spaghetti' }], disclaimer: 'AI may err.' };
		const api = createApi({
			baseUrl: BASE_URL,
			getToken: async () => null,
			fetch: async () => json(200, body)
		});
		await expect(api.recommendations.create('pasta')).resolves.toEqual(body);

		const broken = createApi({
			baseUrl: BASE_URL,
			getToken: async () => null,
			fetch: async () => json(200, { recommendations: 'Spaghetti' })
		});
		await expect(broken.recommendations.create('pasta')).rejects.toMatchObject({
			code: 'INVALID_RESPONSE'
		});
	});
});
