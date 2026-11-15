/**
 * Data for the Impressum (legal notice, § 5 DDG and § 18 Abs. 2 MStV).
 *
 * TODO: These are FICTITIOUS placeholder values. Replace them with the real
 * responsible persons and a postal address before the app is published.
 */
export const impressum = {
	projectName: 'AI Shopping List',
	operators: ['Lena Brandt', 'Jonas Keller'],
	street: 'Beispielweg 12',
	postalCode: '12345',
	city: 'Musterstadt',
	country: 'Deutschland',
	email: 'kontakt@example.org',
	/** Person responsible for the content according to § 18 Abs. 2 MStV. */
	contentResponsible: 'Lena Brandt'
} as const;
