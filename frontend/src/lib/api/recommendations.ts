import type { ApiClient } from './client';
import type { RecommendationResponse } from './types';
import { expectShape, isRecommendationResponse } from './validate';

/**
 * Client timeout for `POST /recommendations`. It must be longer than the backend's
 * Ollama timeout (30 s by default), so that the backend can still answer `AI_TIMEOUT`.
 */
export const RECOMMENDATION_TIMEOUT_MS = 45_000;

/** Endpoint for AI recommendations (`/recommendations`). Nothing is stored on the backend. */
export interface RecommendationsApi {
	create(prompt: string, signal?: AbortSignal): Promise<RecommendationResponse>;
}

export function createRecommendationsApi(client: ApiClient): RecommendationsApi {
	return {
		async create(prompt, signal) {
			const data = await client.request('POST', '/recommendations', {
				body: { prompt },
				timeoutMs: RECOMMENDATION_TIMEOUT_MS,
				signal
			});
			return expectShape(data, isRecommendationResponse);
		}
	};
}
