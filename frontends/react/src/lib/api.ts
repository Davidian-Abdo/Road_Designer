import type { DesignConfigIn, JobStatus, PreviewPayload } from "./types";

// Build-time env var — see .env.example. Falls back to localhost for local
// dev against `uvicorn backend.app.main:app` (default port 8000).
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseErrorBody(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((d: { msg?: string; loc?: unknown }) => d.msg ?? JSON.stringify(d))
        .join("; ");
    }
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return res.statusText;
  }
}

export async function createDesign(params: {
  axeFile: File;
  terrainFile: File | null;
  config: DesignConfigIn;
}): Promise<{ job_id: string; status: "queued" }> {
  const form = new FormData();
  form.append("axe", params.axeFile);
  if (params.terrainFile) {
    form.append("terrain", params.terrainFile);
  }
  form.append("config", JSON.stringify(params.config));

  const res = await fetch(`${API_BASE_URL}/designs`, { method: "POST", body: form });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorBody(res));
  }
  return res.json();
}

export async function getDesignStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE_URL}/designs/${jobId}`);
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorBody(res));
  }
  return res.json();
}

export async function getPreview(jobId: string): Promise<PreviewPayload> {
  const res = await fetch(`${API_BASE_URL}/designs/${jobId}/preview`);
  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorBody(res));
  }
  return res.json();
}

export function fileDownloadUrl(relativeUrl: string): string {
  // Backend returns paths like "/designs/{id}/files/dxf".
  return `${API_BASE_URL}${relativeUrl}`;
}
