export const JOB_PHASES = [
  "queued",
  "planning",
  "searching",
  "writing",
  "email",
  "done",
] as const;

export type Phase = (typeof JOB_PHASES)[number];
export type TerminalPhase = "rejected" | "error";
export type StatusPhase = Phase | TerminalPhase;

export interface StartResponse {
  job_id: string;
}

export interface StatusResponse {
  job_id: string;
  phase: StatusPhase;
  detail: string | null;
}

export type UiState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "running"; jobId: string; phase: Phase; detail?: string | null }
  | { kind: "done"; jobId: string }
  | { kind: "rejected"; jobId: string; detail: string | null }
  | { kind: "error"; message: string };
