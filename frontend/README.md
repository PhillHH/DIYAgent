# Home Task AI – Frontend

> React/Vite-App, die Heimwerker:innen bei Planung, Einkauf und Status-Tracking ihrer Projekte unterstützt.

## Schnellzugriff
- [Backend-README](../README.md) – Gesamtsystem & Docs-Index
- [API-Dokumentation](../api/README.md) – Endpunkte & Statusformat
- [Statusmodell](../orchestrator/README.md) – Phasenübersicht für das Stepper-UI
- [Tailwind-Konfiguration](tailwind.config.js) – Theme & Plugins

## Voraussetzungen
- Node.js 18+
- npm 9+

## Setup
```bash
cd frontend
npm install
```

Konfigurierbare Basis-URL: `.env.development` setzt `VITE_API_BASE=http://127.0.0.1:8005`. Für andere Targets entsprechend anpassen.

## Entwicklungs-Workflow
```bash
# Dev-Server (http://localhost:5173)
npm run dev -- --host 127.0.0.1

# Statischer Produktionsbuild
npm run build

# ESLint prüfen
npm run lint
```

Der Dev-Server kommuniziert mit dem FastAPI-Backend (Standard-Port 8005, siehe `scripts/dev.(ps1|sh)` im Projektstamm). CORS erlaubt `http://localhost:5173` sowie `http://127.0.0.1:5173`.

## Architektur & Komponenten
- **`src/App.tsx`** – Steuert UI-State (`idle → submitting → running → done/rejected/error`), Polling, Toaster-Benachrichtigungen.
- **`src/components/Hero.tsx`** – Intro-Sektion mit Animationen (Framer Motion) und Datenschutz-Hinweis.
- **`src/components/RequestCard.tsx`** – Formular (React Hook Form + Zod), Validierung, Feature-Karten, Toast-Trigger.
- **`src/components/StatusStepper.tsx`** – Phasenanzeige inkl. spezieller Darstellung für `rejected`.
- **`src/api.ts`** – Axios-Client, `startResearch` (POST `/start_research`), `getStatus` (GET `/status/{job_id}`) mit Abort-Unterstützung.
- **`src/index.css`** – Einziger Tailwind-v4-Einstieg mit `@import "tailwindcss"`, Theme-Tokens & Custom Styles (Gradienten, Glas-Effekt, Buttons).

Weitere Assets (z. B. Icons von `lucide-react`) werden direkt in den Komponenten importiert.

## State-Handling & Polling
- Neue Jobs erzeugen einen `AbortController`, laufende Anfragen werden beim erneuten Absenden sauber abgebrochen.
- Polling-Intervall 2000 ms, exponentieller Backoff bis max. 30 s bei 429/5xx.
- Statusbanner & Toasts zeigen Übergänge (`done`, `error`, `rejected`) in deutscher Sprache. Bei `done` kann optional `payload.email_links` (Bauhaus-Links) angezeigt/verarbeitet werden.

## Styling & Interaktionen
- Tailwind CSS v4 + `@tailwindcss/forms`/`@tailwindcss/typography`.
- Helle Stein- und Beigetöne, smaragdgrüne Akzente sowie weiche Schatten werden zentral in `index.css` gepflegt.
- Motion-Effekte (Fade/Slide) via `framer-motion`, Toasts mit `sonner`.

## Tests & Linting
- UI-spezifische Tests aktuell nicht enthalten; Backend-API-Tests siehe [`../tests/README.md`](../tests/README.md).
- `npm run lint` stellt Einhaltung der ESLint-Regeln sicher (TypeScript + React). Optional können Vite-eigene Preview-Tests (`npm run preview`) genutzt werden.

## Weiterführende Aufgaben
- Accessibility-Feinschliff (Kontrast, Tastaturfokus, Screenreader-Texte) erweitern.
- Upload/Attachment-Fluss evaluieren, sobald Premium-Report-Screenshots verfügbar sind.
- Storybook oder Playwright hinzufügen, falls UI-Komponenten separat getestet werden sollen.
