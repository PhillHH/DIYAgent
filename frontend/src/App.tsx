import axios from "axios";
import type { JSX } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Toaster, toast } from "sonner";

import { getStatus } from "./api";
import Hero from "./components/Hero";
import RequestCard from "./components/RequestCard";
import StatusStepper from "./components/StatusStepper";
import { JOB_PHASES, type Phase, type UiState } from "./types";

function App(): JSX.Element {
  const [uiState, setUiState] = useState<UiState>({ kind: "idle" });

  const requestControllerRef = useRef<AbortController | null>(null);
  const pollingControllerRef = useRef<AbortController | null>(null);
  const previousKindRef = useRef<UiState["kind"]>("idle");

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

      const poll = async (): Promise<void> => {
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

  const handleSubmitStart = useCallback(() => {
    cleanupControllers();
    setUiState({ kind: "submitting" });
  }, [cleanupControllers]);

  const handleRegisterRequestController = useCallback((controller: AbortController | null) => {
    requestControllerRef.current = controller;
  }, []);

  const handleStart = useCallback(
    (jobId: string) => {
      requestControllerRef.current = null;
      setUiState({ kind: "running", jobId, phase: "queued" });
      startPolling(jobId);
    },
    [startPolling],
  );

  const handleError = useCallback((message: string) => {
    setUiState({ kind: "error", message });
  }, []);

  const currentDetail = useMemo(() => {
    if (uiState.kind === "running") {
      return uiState.detail ?? null;
    }
    if (uiState.kind === "rejected") {
      return uiState.detail;
    }
    if (uiState.kind === "error") {
      return uiState.message;
    }
    return null;
  }, [uiState]);

  const stepperDetail = useMemo(() => {
    if (uiState.kind === "running") {
      return uiState.detail ?? null;
    }
    if (uiState.kind === "rejected") {
      return uiState.detail;
    }
    return null;
  }, [uiState]);

  useEffect(() => {
    const previousKind = previousKindRef.current;

    if (uiState.kind === "done" && previousKind !== "done") {
      toast.success("Home Task AI hat deinen Projektplan verschickt – bitte Posteingang prüfen.");
    } else if (uiState.kind === "error" && previousKind !== "error") {
      toast.error(uiState.message ?? "Unbekannter Fehler");
    } else if (uiState.kind === "rejected" && previousKind !== "rejected") {
      toast.error(uiState.detail ?? "Anfrage liegt außerhalb des zulässigen Scopes.");
    }

    previousKindRef.current = uiState.kind;
  }, [uiState]);

  const showSuccessBanner = uiState.kind === "done";
  const showErrorBanner = uiState.kind === "rejected" || uiState.kind === "error";

  const errorCardClass = `card-glass ${
    uiState.kind === "rejected"
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : "border-rose-200 bg-rose-100/70 text-rose-700"
  }`;

  return (
    <>
      <div className="page">
        <div className="page-container">
          <Hero />

          {showSuccessBanner && (
            <div role="alert" className="card-glass border-emerald-200 bg-emerald-50 text-emerald-700">
              <strong className="block text-emerald-700">E-Mail versendet.</strong>
              <span>Bitte Posteingang prüfen. Dein Projekt-Report trifft gleich ein.</span>
            </div>
          )}

          {showErrorBanner && (
            <div role="alert" className={errorCardClass}>
              <strong className="block text-rose-700">
                {uiState.kind === "rejected" ? "Anfrage konnte nicht verarbeitet werden." : "Es ist ein Fehler aufgetreten."}
              </strong>
              {currentDetail && <span className="text-rose-600/80">{currentDetail}</span>}
            </div>
          )}

          <RequestCard
            isRunning={uiState.kind === "running" || uiState.kind === "submitting"}
            onSubmitStart={handleSubmitStart}
            onRegisterRequestController={handleRegisterRequestController}
            onStart={handleStart}
            onError={handleError}
            extractErrorMessage={extractErrorMessage}
          />

          <StatusStepper uiState={uiState} detail={stepperDetail} />

          <footer className="pb-6 text-center text-xs text-stone-500">
            © {new Date().getFullYear()} Home Task AI · Dein digitaler Heimwerker-Planer
      </footer>
    </div>
      </div>
      <Toaster richColors theme="light" position="top-center" closeButton />
    </>
  );
}

export default App;
