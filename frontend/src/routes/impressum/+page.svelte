<!-- Legal notice. German on purpose: it is required by German law. Public, no sign-in needed. -->
<script lang="ts">
	import { impressum } from '#lib/legal/impressum.ts';
</script>

<svelte:head>
	<title>Impressum · AI Shopping List</title>
</svelte:head>

<article lang="de" class="mx-auto max-w-2xl space-y-6 card text-sm leading-relaxed text-slate-700">
	<h1 class="text-2xl font-semibold text-slate-900">Impressum</h1>

	<section class="space-y-2">
		<h2 class="text-base font-semibold text-slate-900">Angaben gemäß § 5 DDG</h2>
		<address class="not-italic">
			{impressum.operators.join(' und ')}<br />
			{impressum.street}<br />
			{impressum.postalCode}
			{impressum.city}<br />
			{impressum.country}
		</address>
	</section>

	<section class="space-y-2">
		<h2 class="text-base font-semibold text-slate-900">Kontakt</h2>
		<p>
			E-Mail: <a class="link" href="mailto:{impressum.email}">{impressum.email}</a>
		</p>
	</section>

	<section class="space-y-2">
		<h2 class="text-base font-semibold text-slate-900">
			Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV
		</h2>
		<address class="not-italic">
			{impressum.contentResponsible}<br />
			{impressum.street}<br />
			{impressum.postalCode}
			{impressum.city}
		</address>
	</section>

	<section class="space-y-2">
		<h2 class="text-base font-semibold text-slate-900">Hinweis</h2>
		<p>
			„{impressum.projectName}“ ist ein nicht-kommerzielles Studienprojekt. Die Einkaufsvorschläge
			werden von einer KI erzeugt und können Fehler enthalten. Für ihre Richtigkeit und
			Vollständigkeit wird keine Gewähr übernommen.
		</p>
	</section>

	<section class="space-y-2">
		<h2 class="text-base font-semibold text-slate-900">Haftung für Links</h2>
		<p>
			Diese Website enthält gegebenenfalls Links zu externen Websites Dritter, auf deren Inhalte wir
			keinen Einfluss haben. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter
			oder Betreiber verantwortlich.
		</p>
	</section>
</article>
