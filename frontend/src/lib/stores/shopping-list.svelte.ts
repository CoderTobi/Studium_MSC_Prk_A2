import { SvelteSet } from 'svelte/reactivity';
import {
	toApiError,
	type ApiError,
	type Item,
	type ItemSource,
	type ItemsApi
} from '#lib/api/index.ts';
import { BATCH_MAX_ITEMS } from '#lib/api/limits.ts';

export type LoadState = 'idle' | 'loading' | 'ready' | 'error';

/**
 * State of the user's shopping list. Changes are applied after the backend confirmed
 * them, so the list always shows what is stored.
 *
 * Create one instance per signed-in page, so no state survives a sign-out.
 */
export class ShoppingListStore {
	#items = $state<Item[]>([]);
	#loadState = $state<LoadState>('idle');
	#loadError = $state<ApiError | null>(null);
	#removeError = $state<ApiError | null>(null);
	#adding = $state(false);
	readonly #removing = new SvelteSet<string>();
	readonly #api: ItemsApi;

	constructor(api: ItemsApi) {
		this.#api = api;
	}

	/** Items in the order they were added, oldest first. */
	get items(): readonly Item[] {
		return this.#items;
	}
	get loadState() {
		return this.#loadState;
	}
	/** Error of the last `load()`. */
	get loadError() {
		return this.#loadError;
	}
	/** Error of the last `remove()`. */
	get removeError() {
		return this.#removeError;
	}
	/** `true` while items are being added. */
	get adding() {
		return this.#adding;
	}

	isRemoving(id: string): boolean {
		return this.#removing.has(id);
	}

	dismissRemoveError(): void {
		this.#removeError = null;
	}

	async load(): Promise<void> {
		this.#loadState = 'loading';
		this.#loadError = null;
		try {
			this.#items = await this.#api.list();
			this.#loadState = 'ready';
		} catch (error) {
			this.#loadError = toApiError(error);
			this.#loadState = 'error';
		}
	}

	/**
	 * Adds one item. Resolves to `null` on success, otherwise to the error, so the
	 * caller can show it where the user triggered the action.
	 */
	add(name: string, source: ItemSource = 'manual'): Promise<ApiError | null> {
		return this.#mutate(async () => {
			const item = await this.#api.create({ name: name.trim(), source });
			this.#items.push(item);
		});
	}

	/** Adds several items in one atomic request (all or none). Like `add()` otherwise. */
	addMany(names: readonly string[], source: ItemSource): Promise<ApiError | null> {
		if (names.length === 0) return Promise.resolve(null);
		if (names.length === 1) return this.add(names[0], source);
		if (names.length > BATCH_MAX_ITEMS) {
			throw new RangeError(`At most ${BATCH_MAX_ITEMS} items can be added at once`);
		}
		return this.#mutate(async () => {
			const created = await this.#api.createMany(
				names.map((name) => ({ name: name.trim(), source }))
			);
			this.#items.push(...created);
		});
	}

	async remove(id: string): Promise<void> {
		if (this.#removing.has(id)) return;
		this.#removing.add(id);
		this.#removeError = null;
		try {
			await this.#api.remove(id);
			this.#forget(id);
		} catch (error) {
			const apiError = toApiError(error);
			// Already gone (for example deleted in another tab): the goal is reached.
			if (apiError.code === 'ITEM_NOT_FOUND') this.#forget(id);
			else this.#removeError = apiError;
		} finally {
			this.#removing.delete(id);
		}
	}

	#forget(id: string): void {
		this.#items = this.#items.filter((item) => item.id !== id);
	}

	async #mutate(action: () => Promise<void>): Promise<ApiError | null> {
		this.#adding = true;
		try {
			await action();
			return null;
		} catch (error) {
			return toApiError(error);
		} finally {
			this.#adding = false;
		}
	}
}
