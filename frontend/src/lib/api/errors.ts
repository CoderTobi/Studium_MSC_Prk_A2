import type { ErrorCode, FieldError } from './types';

/**
 * All error codes of the API at runtime. Typing it as `Record<ErrorCode, true>` makes
 * the compiler fail if `api/openapi.yaml` gains or loses a code.
 */
const API_ERROR_CODES: Record<ErrorCode, true> = {
	VALIDATION_ERROR: true,
	PROMPT_EMPTY: true,
	PROMPT_TOO_LONG: true,
	UNAUTHENTICATED: true,
	ITEM_NOT_FOUND: true,
	NOT_FOUND: true,
	METHOD_NOT_ALLOWED: true,
	ITEM_LIMIT_REACHED: true,
	PAYLOAD_TOO_LARGE: true,
	UNSUPPORTED_MEDIA_TYPE: true,
	PROMPT_REJECTED: true,
	RATE_LIMIT_EXCEEDED: true,
	INTERNAL_ERROR: true,
	AI_INVALID_RESPONSE: true,
	AI_UNAVAILABLE: true,
	AI_TIMEOUT: true
};

/**
 * Errors that happen on the client, before or instead of a valid backend response.
 * They are not part of the API.
 */
export type ClientErrorCode =
	/** The backend could not be reached (offline, DNS, CORS, connection refused). */
	| 'NETWORK_ERROR'
	/** The backend did not answer within the client-side timeout. */
	| 'CLIENT_TIMEOUT'
	/** The backend answered with something that does not match the API contract. */
	| 'INVALID_RESPONSE';

export type AppErrorCode = ErrorCode | ClientErrorCode;

const CLIENT_ERROR_MESSAGES: Record<ClientErrorCode, string> = {
	NETWORK_ERROR: 'The server could not be reached. Please check your connection and try again.',
	CLIENT_TIMEOUT: 'The server took too long to respond. Please try again.',
	INVALID_RESPONSE: 'The server sent an unexpected response. Please try again later.'
};

/** Fallback messages in case the backend sends none. Normally its `message` is shown. */
const FALLBACK_MESSAGES: Partial<Record<ErrorCode, string>> = {
	UNAUTHENTICATED: 'Please sign in to continue.',
	RATE_LIMIT_EXCEEDED: 'Too many requests. Please wait a moment and try again.',
	ITEM_LIMIT_REACHED: 'Your shopping list is full. Remove some items first.'
};
const GENERIC_MESSAGE = 'Something went wrong. Please try again later.';

export interface ApiErrorInit {
	code: AppErrorCode;
	/** HTTP status, or 0 if no response was received. */
	status: number;
	message?: string;
	requestId?: string;
	retryAfterSeconds?: number;
	details?: FieldError[];
}

/**
 * Every failure of an API call is an `ApiError`. UI code branches on `code`
 * and may show `message` to the user (it never contains internal details).
 */
export class ApiError extends Error {
	readonly code: AppErrorCode;
	readonly status: number;
	readonly requestId?: string;
	readonly retryAfterSeconds?: number;
	readonly details?: FieldError[];

	constructor(init: ApiErrorInit) {
		super(init.message || defaultMessage(init.code));
		this.name = 'ApiError';
		this.code = init.code;
		this.status = init.status;
		this.requestId = init.requestId;
		this.retryAfterSeconds = init.retryAfterSeconds;
		this.details = init.details;
	}
}

function defaultMessage(code: AppErrorCode): string {
	if (code in CLIENT_ERROR_MESSAGES) return CLIENT_ERROR_MESSAGES[code as ClientErrorCode];
	return FALLBACK_MESSAGES[code as ErrorCode] ?? GENERIC_MESSAGE;
}

export function isApiErrorCode(value: unknown): value is ErrorCode {
	return typeof value === 'string' && Object.hasOwn(API_ERROR_CODES, value);
}

/** Turns anything thrown into an `ApiError`, so UI code only has to handle one type. */
export function toApiError(error: unknown): ApiError {
	if (error instanceof ApiError) return error;
	return new ApiError({ code: 'INTERNAL_ERROR', status: 0 });
}
