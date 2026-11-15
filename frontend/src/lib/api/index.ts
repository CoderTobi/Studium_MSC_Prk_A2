import { ApiClient, type ApiClientOptions } from './client';
import { createItemsApi, type ItemsApi } from './items';
import { createRecommendationsApi, type RecommendationsApi } from './recommendations';

export { ApiClient, type ApiClientOptions, type TokenProvider } from './client';
export { ApiError, toApiError, type AppErrorCode } from './errors';
export type { ItemsApi } from './items';
export type { RecommendationsApi } from './recommendations';
export type * from './types';

/** Everything the UI can do with the backend. */
export interface Api {
	items: ItemsApi;
	recommendations: RecommendationsApi;
}

export function createApi(options: ApiClientOptions): Api {
	const client = new ApiClient(options);
	return {
		items: createItemsApi(client),
		recommendations: createRecommendationsApi(client)
	};
}
