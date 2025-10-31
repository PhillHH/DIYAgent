import axios from "axios";

import type { StartResponse, StatusResponse } from "./types";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8005",
});

/**
 * Startet eine neue Recherche beim Backend.
 * Noch Platzhalter – Fehlerbehandlung und Auth folgen spaeter.
 */
export async function startResearch(
  payload: { email: string; query: string },
  signal?: AbortSignal,
): Promise<StartResponse> {
  const { data } = await client.post<StartResponse>("/start_research", payload, {
    signal,
  });
  return data;
}

/**
 * Fragt den aktuellen Status eines Jobs ab.
 */
export async function getStatus(jobId: string, signal?: AbortSignal): Promise<StatusResponse> {
  const { data } = await client.get<StatusResponse>(`/status/${jobId}`, {
    signal,
  });
  return data;
}
