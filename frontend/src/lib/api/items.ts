import type { ApiClient } from './client';
import type { Item, ItemId, NewItem } from './types';
import { expectShape, isItem, isItemList } from './validate';

/** Endpoints for the user's shopping list (`/items`). */
export interface ItemsApi {
	/** All items, oldest first. */
	list(): Promise<Item[]>;
	create(item: NewItem): Promise<Item>;
	/** Creates all items atomically; they come back in request order. */
	createMany(items: NewItem[]): Promise<Item[]>;
	/** Deletes an item. A missing item or one of another user fails with `ITEM_NOT_FOUND`. */
	remove(id: ItemId): Promise<void>;
}

export function createItemsApi(client: ApiClient): ItemsApi {
	return {
		async list() {
			return expectShape(await client.request('GET', '/items'), isItemList).items;
		},
		async create(item) {
			return expectShape(await client.request('POST', '/items', { body: item }), isItem);
		},
		async createMany(items) {
			const data = await client.request('POST', '/items/batch', { body: { items } });
			return expectShape(data, isItemList).items;
		},
		async remove(id) {
			await client.request('DELETE', `/items/${encodeURIComponent(id)}`);
		}
	};
}
