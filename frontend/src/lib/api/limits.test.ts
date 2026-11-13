import { describe, expect, it } from 'vitest';
import {
	ITEM_NAME_MAX_LENGTH,
	PROMPT_MAX_LENGTH,
	textLength,
	validateItemName,
	validatePrompt
} from './limits.ts';

describe('textLength', () => {
	it('counts Unicode code points like the backend', () => {
		expect(textLength('abc')).toBe(3);
		expect(textLength('🍝🍅')).toBe(2);
	});
});

describe('validateItemName', () => {
	it('accepts valid names', () => {
		expect(validateItemName('Milk')).toBeNull();
		expect(validateItemName('  Milk  ')).toBeNull();
		expect(validateItemName('🍅'.repeat(ITEM_NAME_MAX_LENGTH))).toBeNull();
	});

	it('rejects empty, too long and control characters', () => {
		expect(validateItemName('   ')).toMatch(/enter/);
		expect(validateItemName('a'.repeat(ITEM_NAME_MAX_LENGTH + 1))).toMatch(/longer/);
		expect(validateItemName('Mi\u0000lk')).toMatch(/invalid/);
		expect(validateItemName('Mi\tlk')).toMatch(/invalid/);
	});
});

describe('validatePrompt', () => {
	it('accepts prompts up to the limit after trimming', () => {
		expect(validatePrompt('Pasta for two')).toBeNull();
		expect(validatePrompt(`  ${'a'.repeat(PROMPT_MAX_LENGTH)}  `)).toBeNull();
	});

	it('rejects empty and too long prompts', () => {
		expect(validatePrompt(' \n ')).toMatch(/describe/);
		expect(validatePrompt('a'.repeat(PROMPT_MAX_LENGTH + 1))).toMatch(/longer/);
	});
});
