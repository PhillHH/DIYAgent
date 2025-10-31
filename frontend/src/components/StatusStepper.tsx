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
      <h2 className="text-xl font-semibold text-white">Status</h2>

      <motion.ol className="mt-8 grid gap-4 md:grid-cols-6" initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.05 } } }}>
        {JOB_PHASES.map((phase, index) => {
          const isCompleted = activeIndex > index && !isRejected;
          const isActive = activeIndex === index && !isRejected;
          const isPending = activeIndex < index || activeIndex === -1;
          const isClosingStep = phase === "done";

          const baseClass = clsx(
            "relative flex flex-col gap-3 rounded-2xl border px-4 py-4 text-sm transition",
            isCompleted && "border-emerald-400/60 bg-emerald-400/15 text-emerald-100",
            isActive && "border-lime-300/60 bg-white/10 text-slate-100 shadow-glow",
            isPending && "border-white/10 bg-white/5 text-slate-400",
          );

          const indicatorClass = clsx(
            "flex h-9 w-9 items-center justify-center rounded-full",
            isCompleted && "bg-emerald-400 text-slate-900",
            isActive && "bg-lime-300 text-slate-900",
            isPending && "bg-white/10 text-slate-400",
          );

          return (
            <motion.li key={phase} className={baseClass} variants={itemVariants} layout>
              <div className="flex items-center gap-3">
                <span className={indicatorClass}>{isCompleted ? <CheckIcon /> : index + 1}</span>
                <span className="font-semibold uppercase tracking-wide">{PHASE_LABELS[phase]}</span>
              </div>
              {isActive && !detail && !isRejected && <p className="text-xs text-slate-300">Wird aktuell verarbeitet…</p>}
              {isCompleted && <p className="text-xs text-slate-300">Schritt abgeschlossen.</p>}
              {isPending && <p className="text-xs text-slate-500">Ausstehend…</p>}

              {isClosingStep && isRejected && (
                <motion.div
                  className="mt-3 flex items-center gap-2 rounded-xl border border-rose-400/40 bg-rose-500/15 px-3 py-2 text-xs text-rose-100"
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

      <div className="mt-8 space-y-2 text-sm text-slate-300">
        {uiState.kind === "idle" && <p>Noch kein Auftrag gestartet.</p>}
        {uiState.kind === "submitting" && <p>Auftrag wird gestartet…</p>}
        {(uiState.kind === "running" || uiState.kind === "done") && jobId && (
          <p>
            <span className="font-semibold text-slate-100">Job-ID:</span> {jobId}
          </p>
        )}
        {detail && <p className="text-slate-400">{detail}</p>}
        {uiState.kind === "done" && <p>Report wurde erfolgreich verarbeitet und zugestellt.</p>}
        {uiState.kind === "rejected" && (
          <>
            {jobId && (
              <p>
                <span className="font-semibold text-slate-100">Job-ID:</span> {jobId}
              </p>
            )}
            <p className="text-rose-200">Die Anfrage wurde vom Backend abgelehnt.</p>
            {detail && <p className="text-rose-200/80">{detail}</p>}
          </>
        )}
        {uiState.kind === "error" && <p className="text-rose-200">{uiState.message}</p>}
      </div>
    </motion.section>
  );
}

export default StatusStepper;
