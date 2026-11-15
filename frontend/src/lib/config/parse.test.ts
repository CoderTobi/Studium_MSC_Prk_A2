import { describe, expect, it } from 'vitest';
import {
	parseAuthMode,
	parseBackendUrl,
	parseFirebaseApiKey,
	requireFirebaseApiKey
} from './parse.ts';

describe('parseBackendUrl', () => {
	it('accepts http and https URLs and strips trailing slashes', () => {
		expect(parseBackendUrl('http://localhost:8000')).toBe('http://localhost:8000');
		expect(parseBackendUrl(' https://api.example.org/ ')).toBe('https://api.example.org');
		expect(parseBackendUrl('https://example.org/shop//')).toBe('https://example.org/shop');
	});

	it.each([undefined, '', '   '])('rejects a missing value (%j)', (value) => {
		expect(() => parseBackendUrl(value)).toThrow(/must be set/);
	});

	it.each([
		['not a url', /not a valid URL/],
		['ftp://example.org', /http or https/],
		['javascript:alert(1)', /http or https/],
		['http://user:secret@example.org', /credentials/],
		['http://example.org/?x=1', /query/],
		['http://example.org/#top', /fragment/]
	])('rejects %s', (value, message) => {
		expect(() => parseBackendUrl(value)).toThrow(message);
	});
});

describe('parseAuthMode', () => {
	it('accepts firebase and debug', () => {
		expect(parseAuthMode('firebase')).toBe('firebase');
		expect(parseAuthMode('debug')).toBe('debug');
		expect(parseAuthMode(' debug ')).toBe('debug');
	});

	it.each([undefined, '', 'Firebase', 'DEBUG', 'none'])('rejects %j', (value) => {
		expect(() => parseAuthMode(value)).toThrow(/PUBLIC_AUTH_MODE/);
	});
});

describe('parseFirebaseApiKey', () => {
	it('accepts a key and trims it', () => {
		expect(parseFirebaseApiKey(' AIzaSy-abc_123 ')).toBe('AIzaSy-abc_123');
	});

	it.each([undefined, '', '   '])('treats %j as not set', (value) => {
		expect(parseFirebaseApiKey(value)).toBeUndefined();
	});

	it.each(['two words', '"quoted"', 'key\nline'])('rejects %j', (value) => {
		expect(() => parseFirebaseApiKey(value)).toThrow(/PUBLIC_FIREBASE_API_KEY/);
	});
});

describe('requireFirebaseApiKey', () => {
	it('returns the key in firebase mode', () => {
		expect(requireFirebaseApiKey('firebase', 'key')).toBe('key');
	});

	it('requires the key in firebase mode', () => {
		expect(() => requireFirebaseApiKey('firebase', undefined)).toThrow(/PUBLIC_FIREBASE_API_KEY/);
	});

	it('ignores the key in debug mode', () => {
		expect(requireFirebaseApiKey('debug', undefined)).toBeNull();
		expect(requireFirebaseApiKey('debug', 'key')).toBeNull();
	});
});
