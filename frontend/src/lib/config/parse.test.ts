import { describe, expect, it } from 'vitest';
import { parseAuthMode, parseBackendUrl } from './parse.ts';

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
	it('accepts debug', () => {
		expect(parseAuthMode('debug')).toBe('debug');
		expect(parseAuthMode(' debug ')).toBe('debug');
	});

	it.each([undefined, '', 'firebase', 'DEBUG', 'none'])('rejects %j', (value) => {
		expect(() => parseAuthMode(value)).toThrow(/PUBLIC_AUTH_MODE/);
	});
});
