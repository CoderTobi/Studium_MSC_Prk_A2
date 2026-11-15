/**
 * Limits from `api/openapi.yaml`, checked in the UI for quick feedback.
 * The backend remains the authority and checks them again.
 */

/** `ItemName.maxLength` */
export const ITEM_NAME_MAX_LENGTH = 100;
/** `RecommendationRequest.prompt.maxLength` */
export const PROMPT_MAX_LENGTH = 500;
/** `NewItemBatch.items.maxItems` */
export const BATCH_MAX_ITEMS = 20;

const CONTROL_CHARACTER = /\p{Cc}/u;

/** Length in Unicode code points, as the backend counts it (an emoji counts as 1). */
export function textLength(value: string): number {
	return [...value].length;
}

/** Returns an error message, or `null` if the (untrimmed) name is valid. */
export function validateItemName(name: string): string | null {
	const trimmed = name.trim();
	if (!trimmed) return 'Please enter an item name.';
	if (textLength(trimmed) > ITEM_NAME_MAX_LENGTH) {
		return `The name must not be longer than ${ITEM_NAME_MAX_LENGTH} characters.`;
	}
	if (CONTROL_CHARACTER.test(trimmed)) return 'The name contains invalid characters.';
	return null;
}

/** Returns an error message, or `null` if the (untrimmed) prompt is valid. */
export function validatePrompt(prompt: string): string | null {
	const trimmed = prompt.trim();
	if (!trimmed) return 'Please describe what you would like to eat.';
	if (textLength(trimmed) > PROMPT_MAX_LENGTH) {
		return `The prompt must not be longer than ${PROMPT_MAX_LENGTH} characters.`;
	}
	return null;
}
