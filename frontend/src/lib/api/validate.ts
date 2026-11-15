/**
 * Runtime checks for successful responses. The types only describe what the backend
 * should send; these guards make sure the UI never works with anything else.
 */
import { ApiError } from './errors';
import type { Item, ItemList, Recommendation, RecommendationResponse } from './types';

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isItem(value: unknown): value is Item {
	return (
		isRecord(value) &&
		typeof value.id === 'string' &&
		typeof value.name === 'string' &&
		(value.source === 'manual' || value.source === 'ai_recommendation')
	);
}

export function isItemList(value: unknown): value is ItemList {
	return isRecord(value) && Array.isArray(value.items) && value.items.every(isItem);
}

function isRecommendation(value: unknown): value is Recommendation {
	return isRecord(value) && typeof value.name === 'string';
}

export function isRecommendationResponse(value: unknown): value is RecommendationResponse {
	return (
		isRecord(value) &&
		Array.isArray(value.recommendations) &&
		value.recommendations.every(isRecommendation) &&
		typeof value.disclaimer === 'string'
	);
}

/** Returns `value` if it passes `guard`, otherwise throws `INVALID_RESPONSE`. */
export function expectShape<T>(value: unknown, guard: (value: unknown) => value is T): T {
	if (!guard(value)) throw new ApiError({ code: 'INVALID_RESPONSE', status: 200 });
	return value;
}
