import { motion } from "framer-motion";

/**
 * Hero-Bereich der Landingpage mit Titel, Untertitel und Badge-Leiste.
 * Fokus: schnelles Verständnis, worum es beim DIY-Research Agent geht.
 */
export function Hero(): JSX.Element {
  return (
    <motion.section
      className="card-glass"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: "easeOut" }}
    >
      <div className="flex flex-col gap-6 text-center sm:text-left">
        <div className="flex flex-col items-center justify-start gap-3 sm:flex-row sm:items-center sm:gap-4">
          <span className="inline-flex items-center justify-center rounded-full border border-emerald-400/40 bg-emerald-400/15 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-950 shadow-glow">
            Beta
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-slate-200/90 backdrop-blur">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" aria-hidden="true" />
            Datenschutz: E-Mail nur für den Versand
          </span>
        </div>

        <header className="space-y-4">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-50 sm:text-5xl">
            DIY-Research Agent – dein digitaler Werkstattplaner
          </h1>
          <p className="text-lg text-slate-300 sm:max-w-3xl">
            Vollautomatisierte Recherche, Planung und Dokumentation für deine Heimwerker-Projekte. Du stellst die Frage – unser Agent sammelt Quellen,
            strukturiert alles zu einem Premium-Report und liefert dir die E-Mail innerhalb weniger Minuten.
          </p>
        </header>
      </div>
    </motion.section>
  );
}

export default Hero;

