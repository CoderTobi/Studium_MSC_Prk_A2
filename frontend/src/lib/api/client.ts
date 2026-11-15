import { ApiError, isApiErrorCode } from './errors';
import type { FieldError } from './types';

/** Returns the current ID token, or `null` if the request should be sent without one. */
export type TokenProvider = () => Promise<string | null>;

export interface ApiClientOptions {
	/** Base URL of the versioned API, for example `http://localhost:8000/api/v1`. */
	baseUrl: string;
	getToken: TokenProvider;
	/** Called whenever the backend answers `401 UNAUTHENTICATED`. */
	onUnauthenticated?: () => void;
	/** Default client-side timeout in milliseconds. */
	timeoutMs?: number;
	/** Injectable for tests. */
	fetch?: typeof globalThis.fetch;
}

export interface RequestOptions {
	/** JSON request body. */
	body?: unknown;
	/** Overrides the default timeout for this request. */
	timeoutMs?: number;
	/** Lets the caller cancel the request. Cancelling rethrows the `AbortError`. */
	signal?: AbortSignal;
}

export type HttpMethod = 'GET' | 'POST' | 'DELETE';

export const DEFAULT_TIMEOUT_MS = 15_000;

/** The backend's error messages have at most 300 characters (see `ErrorResponse`). */
const MAX_MESSAGE_LENGTH = 300;

/**
 * Small `fetch` wrapper and the only place that knows about HTTP details:
 * base URL, `Authorization` header, timeouts and the uniform error format.
 *
 * Every failure is thrown as an `ApiError`. A successful response returns the parsed
 * JSON body as `unknown`, so callers have to check its shape (see `validate.ts`).
 */
export class ApiClient {
	readonly #options: ApiClientOptions;
	readonly #fetch: typeof globalThis.fetch;

	constructor(options: ApiClientOptions) {
		this.#options = options;
		this.#fetch = options.fetch ?? ((input, init) => globalThis.fetch(input, init));
	}

	async request(method: HttpMethod, path: string, options: RequestOptions = {}): Promise<unknown> {
		const headers = new Headers({ Accept: 'application/json' });
		const token = await this.#options.getToken();
		if (token) headers.set('Authorization', `Bearer ${token}`);

		let body: string | undefined;
		if (options.body !== undefined) {
			headers.set('Content-Type', 'application/json');
			body = JSON.stringify(options.body);
		}

		const timeout = AbortSignal.timeout(
			options.timeoutMs ?? this.#options.timeoutMs ?? DEFAULT_TIMEOUT_MS
		);
		const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

		/** Exceptions from `fetch` or from reading the body, caused by cancelling or the timeout. */
		const abortFailure = (error: unknown): unknown => {
			if (options.signal?.aborted) return error; // cancelled by the caller: rethrow as is
			if (timeout.aborted) return new ApiError({ code: 'CLIENT_TIMEOUT', status: 0 });
			return null;
		};

		let response: Response;
		try {
			response = await this.#fetch(`${this.#options.baseUrl}${path}`, {
				method,
				headers,
				body,
				signal,
				// Authentication uses the bearer token only, never cookies.
				credentials: 'omit',
				cache: 'no-store'
			});
		} catch (error) {
			throw abortFailure(error) ?? new ApiError({ code: 'NETWORK_ERROR', status: 0 });
		}

		const requestId = response.headers.get('X-Request-ID') ?? undefined;

		let data: unknown;
		let hasBody = true;
		try {
			data = response.status === 204 ? undefined : await readJson(response);
		} catch (error) {
			const aborted = abortFailure(error);
			if (aborted) throw aborted;
			hasBody = false;
		}

		if (response.ok) {
			if (!hasBody) {
				throw new ApiError({ code: 'INVALID_RESPONSE', status: response.status, requestId });
			}
			return data;
		}

		const error = hasBody
			? parseError(data, response, requestId)
			: errorWithoutBody(response, requestId);
		if (error.code === 'UNAUTHENTICATED') this.#options.onUnauthenticated?.();
		throw error;
	}
}

async function readJson(response: Response): Promise<unknown> {
	const contentType = response.headers.get('Content-Type') ?? '';
	if (!/^application\/(.+\+)?json\b/i.test(contentType)) {
		throw new TypeError(`Unexpected content type: ${contentType}`);
	}
	return response.json();
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseRetryAfter(value: unknown): number | undefined {
	const seconds = typeof value === 'string' ? Number(value) : value;
	return typeof seconds === 'number' && Number.isInteger(seconds) && seconds >= 0
		? seconds
		: undefined;
}

function parseDetails(value: unknown): FieldError[] | undefined {
	if (!Array.isArray(value)) return undefined;
	return value
		.filter(isRecord)
		.filter(
			(detail): detail is FieldError =>
				typeof detail.field === 'string' && typeof detail.issue === 'string'
		)
		.map(({ field, issue }) => ({ field, issue }));
}

/** Parses an `ErrorResponse` body. Bodies that don't match it are mapped by HTTP status. */
function parseError(data: unknown, response: Response, headerRequestId?: string): ApiError {
	const error = isRecord(data) && isRecord(data.error) ? data.error : undefined;
	if (!error || !isApiErrorCode(error.code)) return errorWithoutBody(response, headerRequestId);

	return new ApiError({
		code: error.code,
		status: response.status,
		message:
			typeof error.message === 'string' ? error.message.slice(0, MAX_MESSAGE_LENGTH) : undefined,
		requestId: typeof error.requestId === 'string' ? error.requestId : headerRequestId,
		retryAfterSeconds:
			parseRetryAfter(error.retryAfterSeconds) ??
			parseRetryAfter(response.headers.get('Retry-After')),
		details: parseDetails(error.details)
	});
}

/** Fallback for error responses without a valid `ErrorResponse` body (for example from a proxy). */
function errorWithoutBody(response: Response, requestId?: string): ApiError {
	switch (response.status) {
		case 401:
			return new ApiError({ code: 'UNAUTHENTICATED', status: 401, requestId });
		case 429:
			return new ApiError({
				code: 'RATE_LIMIT_EXCEEDED',
				status: 429,
				requestId,
				retryAfterSeconds: parseRetryAfter(response.headers.get('Retry-After'))
			});
		default:
			return new ApiError({ code: 'INVALID_RESPONSE', status: response.status, requestId });
	}
}
