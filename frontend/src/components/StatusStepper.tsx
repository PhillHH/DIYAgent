import clsx from "clsx";
import { motion } from "framer-motion";

import { JOB_PHASES, type Phase, type UiState } from "../types";

const PHASE_LABELS: Record<Phase, string> = {
  queued: "Warteschlange",
  planning: "Planung",
  searching: "Recherche",
  writing: "Schreiben",
  email: "E-Mail Versand",
  done: "Abgeschlossen",
};

const itemVariants = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0 },
};

type StatusStepperProps = {
  /** Aktueller UI-Zustand, um Phase und Job-ID anzeigen zu können. */
  uiState: UiState;
  /** Detailnachrichten aus dem Backend (z. B. Fortschrittstexte). */
  detail: string | null;
};

function CheckIcon(props: { className?: string }): JSX.Element {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" className={clsx("h-4 w-4", props.className)}>
      <path
        d="m4 10 4 4 8-8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CrossIcon(props: { className?: string }): JSX.Element {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" className={clsx("h-4 w-4", props.className)}>
      <path d="m5 5 10 10m0-10-10 10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function resolveActivePhase(uiState: UiState): Phase | null {
  if (uiState.kind === "running") {
    return uiState.phase;
  }
  if (uiState.kind === "done" || uiState.kind === "rejected") {
    return "done";
  }
  return null;
}

export function StatusStepper({ uiState, detail }: StatusStepperProps): JSX.Element {
  const activePhase = resolveActivePhase(uiState);
  const activeIndex = activePhase ? JOB_PHASES.indexOf(activePhase) : -1;
  const isRejected = uiState.kind === "rejected";
  const jobId = uiState.kind === "running" || uiState.kind === "done" || uiState.kind === "rejected" ? uiState.jobId : null;

  return (
    <motion.section className="card-glass" aria-live="polite" initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 }}>
      <h2 className="text-xl font-semibold text-stone-800">Projektstatus</h2>

      <motion.ol className="mt-8 grid gap-4 md:grid-cols-6" initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.05 } } }}>
        {JOB_PHASES.map((phase, index) => {
          const isCompleted = activeIndex > index && !isRejected;
          const isActive = activeIndex === index && !isRejected;
          const isPending = activeIndex < index || activeIndex === -1;
          const isClosingStep = phase === "done";

          const baseClass = clsx(
            "relative flex flex-col gap-3 rounded-2xl border px-4 py-4 text-sm transition",
            isCompleted && "border-emerald-300 bg-emerald-100 text-emerald-700",
            isActive && "border-emerald-500 bg-emerald-50 text-emerald-700 shadow-sm",
            isPending && "border-stone-200 bg-white text-stone-400",
          );

          const indicatorClass = clsx(
            "flex h-9 w-9 items-center justify-center rounded-full",
            isCompleted && "bg-emerald-500/90 text-white",
            isActive && "bg-emerald-500 text-white",
            isPending && "bg-stone-100 text-stone-500",
          );

          return (
            <motion.li key={phase} className={baseClass} variants={itemVariants} layout>
              <div className="flex items-center gap-3">
                <span className={indicatorClass}>{isCompleted ? <CheckIcon /> : index + 1}</span>
                <span className="font-semibold uppercase tracking-wide">{PHASE_LABELS[phase]}</span>
              </div>
              {isActive && !detail && !isRejected && <p className="text-xs text-stone-600">Wird aktuell verarbeitet…</p>}
              {isCompleted && <p className="text-xs text-stone-600">Schritt abgeschlossen.</p>}
              {isPending && <p className="text-xs text-stone-400">Ausstehend…</p>}

              {isClosingStep && isRejected && (
                <motion.div
                  className="mt-3 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <CrossIcon />
                  <span>Anfrage wurde abgelehnt.</span>
                </motion.div>
              )}
            </motion.li>
          );
        })}
      </motion.ol>

      <div className="mt-8 space-y-2 text-sm text-stone-600">
        {uiState.kind === "idle" && <p>Noch kein Auftrag gestartet.</p>}
        {uiState.kind === "submitting" && <p>Auftrag wird gestartet…</p>}
        {(uiState.kind === "running" || uiState.kind === "done") && jobId && (
          <p>
            <span className="font-semibold text-stone-800">Job-ID:</span> {jobId}
          </p>
        )}
        {detail && <p className="text-stone-500">{detail}</p>}
        {uiState.kind === "done" && <p>Report wurde erfolgreich verarbeitet und zugestellt.</p>}
        {uiState.kind === "rejected" && (
          <>
            {jobId && (
              <p>
                <span className="font-semibold text-stone-800">Job-ID:</span> {jobId}
              </p>
            )}
            <p className="text-rose-600">Die Anfrage wurde vom Backend abgelehnt.</p>
            {detail && <p className="text-rose-600/80">{detail}</p>}
          </>
        )}
        {uiState.kind === "error" && <p className="text-rose-600">{uiState.message}</p>}
      </div>
    </motion.section>
  );
}

export default StatusStepper;
