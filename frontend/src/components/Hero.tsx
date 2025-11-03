import type { JSX } from "react";

import { WrenchIcon } from "./icons";
export function Hero(): JSX.Element {
  return (
    <section className="bg-gradient-to-br from-amber-50 via-amber-100 to-stone-100">
      <div className="mx-auto max-w-screen-xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:items-center">
          <div className="space-y-6 animate-fade-up" style={{ animationDelay: "0.05s" }}>
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-100 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-700">
              Home Task AI
            </span>

            <div className="space-y-4">
              <h1 className="text-4xl font-semibold text-stone-800 md:text-5xl">
                Home Task AI – Dein smarter DIY-Planer
              </h1>
              <p className="text-lg leading-relaxed text-stone-600">
                Plane, recherchiere und organisiere deine Heimwerkerprojekte – mit KI-Unterstützung. Wir kombinieren klare Schritt-für-Schritt-Anleitungen,
                Materiallisten und realistische Zeitpläne, damit du direkt loslegen kannst.
              </p>
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <button className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-3 font-medium text-white shadow-md transition-transform duration-200 hover:-translate-y-0.5 hover:bg-emerald-600">
                <WrenchIcon className="h-5 w-5" />
                Projekt starten
              </button>
              <a
                href="#einkaufsliste"
                className="text-sm font-medium text-emerald-600 transition hover:text-emerald-700"
              >
                Materialliste ansehen →
              </a>
            </div>
          </div>

          <div
            className="relative overflow-hidden rounded-3xl border border-emerald-100 bg-white/70 shadow-xl animate-fade-up"
            style={{ animationDelay: "0.18s" }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-100/60 via-transparent to-emerald-200/60" aria-hidden="true" />
            <div className="relative p-8">
              <div className="mb-6 flex items-center justify-between text-sm text-stone-500">
                <span className="font-semibold text-stone-700">Projektplanung</span>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-600">Schritt für Schritt</span>
              </div>
              <ul className="space-y-4 text-sm text-stone-600">
                <li className="flex items-start gap-3">
                  <span className="mt-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-xs font-semibold text-white">1</span>
                  <div>
                    <p className="font-medium text-stone-700">Projektbeschreibung strukturieren</p>
                    <p className="text-stone-500">Maße, Budget und gewünschte Materialien erfassen – Home Task AI erkennt fehlende Angaben automatisch.</p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <span className="mt-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-xs font-semibold text-white">2</span>
                  <div>
                    <p className="font-medium text-stone-700">Materialliste mit Bauhaus-Verlinkung</p>
                    <p className="text-stone-500">Direkte Einkaufsliste mit geprüften Links, Preisen und Hinweisen – ohne eigene Recherche.</p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <span className="mt-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-xs font-semibold text-white">3</span>
                  <div>
                    <p className="font-medium text-stone-700">Zeitplan & Qualitätssicherung</p>
                    <p className="text-stone-500">Realistische Zeit- und Kostenplanung mit Sicherheitshinweisen und Prüfkriterien je Schritt.</p>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Hero;

