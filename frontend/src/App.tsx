import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import clsx from "clsx";
import axios from "axios";

import { startResearch, getStatus } from "./api";
import type { StartResponse, Phase } from "./types";
import { JOB_PHASES } from "./types";

// Formularregeln: Pflichtfelder mit Basisvalidierung auf Deutsch.
const formSchema = z.object({
  email: z.string().email({ message: "Bitte eine gültige E-Mail-Adresse eintragen." }),
  query: z
    .string()
    .min(10, "Bitte mindestens 10 Zeichen eingeben.")
    .max(2000, "Die Anfrage darf maximal 2000 Zeichen enthalten."),
});

type FormValues = z.infer<typeof formSchema>;

// UI-State-Maschine für alle Oberflächenzustände.
type UiState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "running"; jobId: string; phase: Phase; detail?: string | null }
  | { kind: "done"; jobId: string }
  | { kind: "rejected"; jobId: string; detail: string | null }
  | { kind: "error"; message: string };

const phaseLabels: Record<Phase, string> = {
  queued: "Warteschlange",
  planning: "Planung",
  searching: "Recherche",
  writing: "Schreiben",
  email: "E-Mail Versand",
  done: "Abgeschlossen",
};

const buttonBase =
  "inline-flex items-center justify-center rounded-full px-6 py-3 text-base font-semibold transition focus:outline-none focus:ring-4";

const inputBase =
  "block w-full rounded-2xl border border-slate-800/80 bg-slate-900/70 px-4 py-3 text-base text-slate-100 shadow-inner placeholder:text-slate-500 transition focus:border-sky-500 focus:ring-4 focus:ring-sky-500/40 focus:outline-none";

function App() {
  const [uiState, setUiState] = useState<UiState>({ kind: "idle" });

  const requestControllerRef = useRef<AbortController | null>(null);
  const pollingControllerRef = useRef<AbortController | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: "", query: "" },
  });

  const activePhaseIndex = useMemo(() => {
    if (uiState.kind === "running") {
      return JOB_PHASES.indexOf(uiState.phase);
    }
    if (uiState.kind === "done") {
      return JOB_PHASES.length - 1;
    }
    return -1;
  }, [uiState]);

  const cleanupControllers = useCallback(() => {
    requestControllerRef.current?.abort();
    requestControllerRef.current = null;
    pollingControllerRef.current?.abort();
    pollingControllerRef.current = null;
  }, []);

  useEffect(() => () => cleanupControllers(), [cleanupControllers]);

  const extractErrorMessage = useCallback((error: unknown): string => {
    if (axios.isAxiosError(error)) {
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
      return detail ?? error.message ?? "Unbekannter Fehler";
    }
    if (error instanceof Error) {
      return error.message;
    }
    return "Unbekannter Fehler";
  }, []);

  const wait = useCallback((ms: number, signal: AbortSignal) => {
    return new Promise<void>((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException("Abgebrochen", "AbortError"));
        return;
      }
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", onAbort);
        resolve();
      }, ms);
      const onAbort = () => {
        clearTimeout(timer);
        reject(new DOMException("Abgebrochen", "AbortError"));
      };
      signal.addEventListener("abort", onAbort, { once: true });
    });
  }, []);

  const startPolling = useCallback(
    (jobId: string) => {
      const controller = new AbortController();
      pollingControllerRef.current = controller;

      const baseDelay = 2000;
      let attempt = 0;

      const poll = async () => {
        if (controller.signal.aborted) {
          return;
        }

        try {
          const status = await getStatus(jobId, controller.signal);
          attempt = 0;

          if (controller.signal.aborted) {
            return;
          }

          if (status.phase === "rejected") {
            pollingControllerRef.current = null;
            setUiState({ kind: "rejected", jobId: status.job_id, detail: status.detail });
            return;
          }

          if (status.phase === "error") {
            pollingControllerRef.current = null;
            setUiState({
              kind: "error",
              message: status.detail ?? "Der Backend-Job wurde mit Fehler beendet.",
            });
            return;
          }

          if (status.phase === "done") {
            pollingControllerRef.current = null;
            setUiState({ kind: "done", jobId: status.job_id });
            return;
          }

          if (JOB_PHASES.includes(status.phase as Phase)) {
            setUiState({
              kind: "running",
              jobId: status.job_id,
              phase: status.phase as Phase,
              detail: status.detail,
            });
          }

          await wait(baseDelay, controller.signal);
          await poll();
        } catch (error) {
          if (controller.signal.aborted) {
            return;
          }

          if (axios.isAxiosError(error)) {
            const code = error.response?.status ?? 0;
            if (code === 429 || code >= 500) {
              attempt += 1;
              const backoff = Math.min(30000, baseDelay * 2 ** Math.min(attempt, 5));
              try {
                await wait(backoff, controller.signal);
                await poll();
              } catch (abortError) {
                if (!(abortError instanceof DOMException && abortError.name === "AbortError")) {
                  setUiState({ kind: "error", message: extractErrorMessage(abortError) });
                }
              }
              return;
            }
          }

          setUiState({ kind: "error", message: extractErrorMessage(error) });
          pollingControllerRef.current = null;
        }
      };

      void poll();
    },
    [extractErrorMessage, wait],
  );

  const onSubmit = handleSubmit(async (values) => {
    cleanupControllers();
    const controller = new AbortController();
    requestControllerRef.current = controller;
    setUiState({ kind: "submitting" });

    try {
      const response: StartResponse = await startResearch(values, controller.signal);
      setUiState({ kind: "running", jobId: response.job_id, phase: "queued" });
      reset(values);
      startPolling(response.job_id);
    } catch (error) {
      if (axios.isAxiosError(error) && error.code === "ERR_CANCELED") {
        return;
      }
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      setUiState({ kind: "error", message: extractErrorMessage(error) });
    }
  });

  const currentDetail =
    uiState.kind === "running"
      ? uiState.detail
      : uiState.kind === "rejected"
      ? uiState.detail
      : uiState.kind === "error"
      ? uiState.message
      : null;

  const showSuccessBanner = uiState.kind === "done";
  const showErrorBanner = uiState.kind === "rejected" || uiState.kind === "error";

  return (
    <div className="min-h-screen bg-slate-950 bg-[radial-gradient(circle_at_top,_#1d4ed8_0%,_rgba(15,23,42,0.9)_55%,_#020617_100%)] px-4 py-10 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-10">
        <section className="rounded-3xl bg-slate-900/60 p-8 shadow-xl shadow-slate-900/40 backdrop-blur">
          {/* Hero-Block: erklärt in einem Satz, was das Tool macht. */}
          <div className="flex flex-col gap-4 text-center sm:text-left">
            <span className="inline-flex items-center justify-center self-center rounded-full border border-sky-400/40 px-4 py-1 text-sm font-medium uppercase tracking-wide text-sky-300 sm:self-start">
              Beta
            </span>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              DIY-Research Agent – dein digitaler Werkstattplaner
            </h1>
            <p className="text-lg text-slate-300">
              Dieses Tool analysiert deine Heimwerkerfrage, plant Recherche-Schritte, sammelt Ergebnisse und erstellt einen ausführlichen DIY-Report. Alles läuft automatisiert – du erhältst das Resultat bequem per E-Mail.
            </p>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-400">
              <strong className="block text-slate-200">Datenschutz-Hinweis</strong>
              Deine E-Mail wird ausschließlich zum Versand des Reports verwendet und nicht gespeichert.
            </div>
          </div>
        </section>

        {showSuccessBanner && (
          <div role="alert" className="rounded-2xl border border-emerald-400/40 bg-emerald-500/15 p-4 text-emerald-100">
            <strong className="block">E-Mail versendet.</strong>
            <span>Bitte Posteingang prüfen. Der Bericht sollte in wenigen Minuten eintreffen.</span>
          </div>
        )}

        {showErrorBanner && (
          <div
            role="alert"
            className="rounded-2xl border border-rose-500/40 bg-rose-500/15 p-4 text-rose-100"
          >
            <strong className="block">
              {uiState.kind === "rejected" ? "Anfrage konnte nicht verarbeitet werden." : "Es ist ein Fehler aufgetreten."}
            </strong>
            {currentDetail && <span>{currentDetail}</span>}
          </div>
        )}

        <div className="grid gap-8 lg:grid-cols-2">
          <section className="rounded-3xl border border-slate-800 bg-slate-900/70 p-8 shadow-lg shadow-slate-900/40 backdrop-blur">
            {/* Formular zum Starten einer neuen Recherche mit reaktiver Validierung. */}
            <h2 className="text-xl font-semibold text-white">Report anfordern</h2>
            <form className="mt-6 space-y-5" onSubmit={onSubmit}>
              <div className="space-y-2">
                <label htmlFor="email" className="block text-sm font-medium text-slate-300">
                  E-Mail-Adresse
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="dein.name@example.com"
                  className={inputBase}
                  {...register("email")}
                  disabled={uiState.kind === "running"}
                  aria-invalid={errors.email ? "true" : "false"}
                  aria-describedby={errors.email ? "email-error" : undefined}
                />
                {errors.email && (
                  <span id="email-error" className="text-sm text-rose-300">
                    {errors.email.message}
                  </span>
                )}
              </div>

              <div className="space-y-2">
                <label htmlFor="query" className="block text-sm font-medium text-slate-300">
                  Heimwerker-Anfrage
                </label>
                <textarea
                  id="query"
                  rows={6}
                  placeholder="Beschreibe kurz dein Projekt – z. B. Laminat im Flur verlegen samt Materialliste."
                  className={clsx(inputBase, "resize-vertical")}
                  {...register("query")}
                  disabled={uiState.kind === "running"}
                  aria-invalid={errors.query ? "true" : "false"}
                  aria-describedby={errors.query ? "query-error" : undefined}
                />
                {errors.query && (
                  <span id="query-error" className="text-sm text-rose-300">
                    {errors.query.message}
                  </span>
                )}
              </div>

              <button
                type="submit"
                className={clsx(buttonBase, "bg-sky-500 text-white shadow-lg shadow-sky-500/30 hover:bg-sky-400 focus:ring-sky-500/40 disabled:cursor-wait disabled:opacity-60")}
                disabled={isSubmitting || uiState.kind === "running"}
              >
                {uiState.kind === "submitting" || isSubmitting ? "Wird gesendet…" : "DIY-Report anfordern"}
              </button>
            </form>
          </section>

          <section
            className="rounded-3xl border border-slate-800 bg-slate-900/70 p-8 shadow-lg shadow-slate-900/40 backdrop-blur"
            aria-live="polite"
          >
            {/* Statuskarte mit Stepper zur Visualisierung der Backend-Phasen. */}
            <h2 className="text-xl font-semibold text-white">Status</h2>
            <ol className="mt-6 flex flex-col gap-3">
              {JOB_PHASES.map((phase, index) => (
                <li
                  key={phase}
                  className={clsx(
                    "flex items-center gap-3 rounded-2xl border px-4 py-3",
                    activePhaseIndex > index && "border-emerald-500/50 bg-emerald-500/10 text-emerald-200",
                    activePhaseIndex === index && "border-sky-500/60 bg-sky-500/15 text-sky-200",
                    activePhaseIndex < index && "border-slate-800 bg-slate-900 text-slate-400",
                  )}
                >
                  <span
                    className={clsx(
                      "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
                      activePhaseIndex > index && "bg-emerald-500 text-slate-900",
                      activePhaseIndex === index && "bg-sky-500 text-slate-900",
                      activePhaseIndex < index && "bg-slate-800 text-slate-400",
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="text-sm font-medium uppercase tracking-wide">
                    {phaseLabels[phase]}
                  </span>
                </li>
              ))}
            </ol>

            <div className="mt-6 space-y-2 text-sm text-slate-300">
              {uiState.kind === "idle" && <p>Noch kein Auftrag gestartet.</p>}
              {uiState.kind === "submitting" && <p>Auftrag wird gestartet…</p>}
              {uiState.kind === "running" && (
                <>
                  <p>
                    <span className="font-semibold text-slate-100">Job-ID:</span> {uiState.jobId}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-100">Aktuelle Phase:</span> {phaseLabels[uiState.phase]}
                  </p>
                  {uiState.detail && <p className="text-slate-400">{uiState.detail}</p>}
                </>
              )}
              {uiState.kind === "done" && (
                <>
                  <p>
                    <span className="font-semibold text-slate-100">Job-ID:</span> {uiState.jobId}
                  </p>
                  <p>Report wurde erfolgreich verarbeitet und zugestellt.</p>
                </>
              )}
              {uiState.kind === "rejected" && (
                <>
                  <p>
                    <span className="font-semibold text-slate-100">Job-ID:</span> {uiState.jobId}
                  </p>
                  <p>Die Anfrage wurde vom Backend abgelehnt.</p>
                  {uiState.detail && <p className="text-slate-400">{uiState.detail}</p>}
                </>
              )}
              {uiState.kind === "error" && <p>{uiState.message}</p>}
            </div>
          </section>
        </div>

        <footer className="pb-6 text-center text-xs text-slate-500">
          © {new Date().getFullYear()} DIY Research Agent · Erstellt als Forschungsprototyp
        </footer>
      </div>
    </div>
  );
}

export default App;
