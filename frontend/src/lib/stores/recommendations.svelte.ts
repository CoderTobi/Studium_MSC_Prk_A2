import { toApiError, type ApiError, type RecommendationsApi } from '#lib/api/index.ts';

export interface Suggestion {
	/** Local key, stable while the suggestion is shown. */
	readonly key: number;
	readonly name: string;
	selected: boolean;
}

export type RecommendationsState = 'idle' | 'loading' | 'ready' | 'error';

/** Adds the given names to the shopping list. Resolves to `null` on success, else the error. */
export type AddToList = (names: string[]) => Promise<ApiError | null>;

/**
 * State of the AI recommendations: the current suggestions, which of them are
 * selected, and accepting or discarding them.
 *
 * Suggestions are never stored on the backend. Accepting adds them to the list through
 * `addToList`; discarding simply forgets them.
 */
export class RecommendationsStore {
	#state = $state<RecommendationsState>('idle');
	#suggestions = $state<Suggestion[]>([]);
	#disclaimer = $state('');
	#requestError = $state<ApiError | null>(null);
	#acceptError = $state<ApiError | null>(null);
	#accepting = $state(false);
	#controller: AbortController | null = null;
	#nextKey = 0;
	readonly #api: RecommendationsApi;
	readonly #addToList: AddToList;

	constructor(api: RecommendationsApi, addToList: AddToList) {
		this.#api = api;
		this.#addToList = addToList;
	}

	get state() {
		return this.#state;
	}
	get suggestions(): readonly Suggestion[] {
		return this.#suggestions;
	}
	get selectedCount(): number {
		return this.#suggestions.filter((suggestion) => suggestion.selected).length;
	}
	/** Fixed text from the backend saying that AI may make mistakes. */
	get disclaimer() {
		return this.#disclaimer;
	}
	/** Error of the last `request()`. */
	get requestError() {
		return this.#requestError;
	}
	/** Error of the last accept; the suggestions are kept so the user can retry. */
	get acceptError() {
		return this.#acceptError;
	}
	get accepting() {
		return this.#accepting;
	}

	/** Asks the backend for suggestions. A request that is still running is cancelled. */
	async request(prompt: string): Promise<void> {
		this.#controller?.abort();
		const controller = new AbortController();
		this.#controller = controller;

		this.#state = 'loading';
		this.#requestError = null;
		this.#acceptError = null;
		try {
			const response = await this.#api.create(prompt.trim(), controller.signal);
			this.#suggestions = response.recommendations.map(({ name }) => ({
				key: this.#nextKey++,
				name,
				selected: true
			}));
			this.#disclaimer = response.disclaimer;
			this.#state = 'ready';
		} catch (error) {
			if (controller.signal.aborted) return;
			this.#suggestions = [];
			this.#requestError = toApiError(error);
			this.#state = 'error';
		} finally {
			if (this.#controller === controller) this.#controller = null;
		}
	}

	/** Cancels a running request and keeps the previous suggestions, if any. */
	cancel(): void {
		if (!this.#controller) return;
		this.#controller.abort();
		this.#controller = null;
		this.#state = this.#suggestions.length > 0 ? 'ready' : 'idle';
	}

	toggle(key: number): void {
		const suggestion = this.#suggestions.find((candidate) => candidate.key === key);
		if (suggestion) suggestion.selected = !suggestion.selected;
	}

	selectAll(selected: boolean): void {
		for (const suggestion of this.#suggestions) suggestion.selected = selected;
	}

	/** Adds the selected suggestions to the list and removes them from the suggestions. */
	acceptSelected(): Promise<boolean> {
		return this.#accept(this.#suggestions.filter((suggestion) => suggestion.selected));
	}

	/** Adds a single suggestion to the list. */
	acceptOne(key: number): Promise<boolean> {
		return this.#accept(this.#suggestions.filter((suggestion) => suggestion.key === key));
	}

	/** Drops all suggestions. Nothing is sent to the backend. */
	discard(): void {
		this.cancel();
		this.#suggestions = [];
		this.#disclaimer = '';
		this.#requestError = null;
		this.#acceptError = null;
		this.#state = 'idle';
	}

	dismissRequestError(): void {
		this.#requestError = null;
		if (this.#state === 'error') this.#state = 'idle';
	}

	dismissAcceptError(): void {
		this.#acceptError = null;
	}

	async #accept(accepted: Suggestion[]): Promise<boolean> {
		if (accepted.length === 0 || this.#accepting) return false;
		this.#accepting = true;
		this.#acceptError = null;
		try {
			const error = await this.#addToList(accepted.map((suggestion) => suggestion.name));
			if (error) {
				this.#acceptError = error;
				return false;
			}
			const keys = accepted.map((suggestion) => suggestion.key);
			this.#suggestions = this.#suggestions.filter((suggestion) => !keys.includes(suggestion.key));
			if (this.#suggestions.length === 0) this.discard();
			return true;
		} finally {
			this.#accepting = false;
		}
	}
}
