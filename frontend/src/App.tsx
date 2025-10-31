import axios from "axios";
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
      toast.success("E-Mail versendet – bitte Posteingang prüfen.");
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
      ? "border-rose-400/40 bg-rose-500/20 text-rose-100"
      : "border-rose-400/40 bg-rose-500/15 text-rose-100"
  }`;

  return (
    <>
      <div className="page">
        <div className="page-container">
          <Hero />

          {showSuccessBanner && (
            <div role="alert" className="card-glass border-emerald-400/40 bg-emerald-400/15 text-emerald-100">
              <strong className="block text-emerald-200">E-Mail versendet.</strong>
              <span>Bitte Posteingang prüfen. Der Bericht sollte in wenigen Minuten eintreffen.</span>
            </div>
          )}

          {showErrorBanner && (
            <div role="alert" className={errorCardClass}>
              <strong className="block text-rose-200">
                {uiState.kind === "rejected" ? "Anfrage konnte nicht verarbeitet werden." : "Es ist ein Fehler aufgetreten."}
              </strong>
              {currentDetail && <span className="text-rose-100/80">{currentDetail}</span>}
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

          <footer className="pb-6 text-center text-xs text-slate-400">
            © {new Date().getFullYear()} DIY Research Agent · Erstellt als Forschungsprototyp
          </footer>
        </div>
      </div>
      <Toaster richColors theme="dark" position="top-center" closeButton />
    </>
  );
}

export default App;
