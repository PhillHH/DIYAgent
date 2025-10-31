# DIY Research Agent – Frontend

Vite + React + TypeScript als leichtgewichtiges UI für den DIY Research Agent. Das Projekt stellt ein Formular zum Anfordern von DIY-Reports bereit und dient als Ausgangspunkt für zukünftige API-Integration.

## Voraussetzungen
- Node.js 18+
- npm 9+

## Setup
```bash
# Abhängigkeiten installieren
npm install
```

TailwindCSS ist bereits vorkonfiguriert. Weitere Envs können in `.env.development` gepflegt werden (Standard: `VITE_API_BASE=http://127.0.0.1:8005`).

## Entwicklung starten
```bash
npm run dev
```
Der Vite-Dev-Server läuft anschließend (Standard: http://localhost:5173). Die Backend-API wird über `VITE_API_BASE` angesprochen.

## Nützliche Scripts
- `npm run dev` – Entwicklungsserver mit HMR
- `npm run build` – Produktionsbuild erzeugen
- `npm run preview` – lokalen Preview-Server starten
- `npm run lint` – ESLint prüfen

## Projektstruktur
```
frontend/
├── src/
│   ├── api.ts          # Axios-Client + Placeholder-Endpunkte
│   ├── App.tsx         # UI-Skeleton für Formular & Status
│   ├── App.css         # Basis-Styles
│   ├── main.tsx        # React-Entry-Point
│   ├── types.ts        # Gemeinsame Typdefinitionen
│   └── index.css       # Globale Basestyles
├── .env.development    # Vite-Env mit VITE_API_BASE
├── index.html          # HTML-Template
└── README.md           # Dieses Dokument
```

## Weitere Schritte
- API-Aufrufe mit Fehlerbehandlung ergänzen, sobald Backend-Endpunkte stabil sind.
- Statuspolling (z. B. via `getStatus`) implementieren.
- UI verfeinern (Loading-States, Validierung, Feedbackmeldungen).
- Optional Authentifizierung/Autorisierung vorsehen.
- CORS im Backend muss `http://localhost:5173` erlauben (bereits in FastAPI hinterlegt).
