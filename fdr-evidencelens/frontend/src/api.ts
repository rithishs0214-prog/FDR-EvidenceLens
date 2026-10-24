export const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";

export class ApiClientError extends Error {
  status: number;
  code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parseError(res: Response): Promise<ApiClientError> {
  try {
    const body = await res.json();
    if (body?.error) return new ApiClientError(body.error.message, res.status, body.error.code);
  } catch { /* fall through */ }
  return new ApiClientError(`The server returned an unexpected error (${res.status}).`, res.status, "http_error");
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (typeof init?.body === "string") headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiClientError(`Cannot reach the backend at ${API_BASE}. Is it running?`, 0, "network_error");
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/")) window.dispatchEvent(new Event("auth:expired"));
    throw await parseError(res);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const get = <T,>(path: string) => api<T>(path);
export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T,>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const patch = <T,>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const del = (path: string) => api<void>(path, { method: "DELETE" });

export function fileUrl(caseId: number, docId: number, download = false): string {
  return `${API_BASE}/api/cases/${caseId}/documents/${docId}/file${download ? "?download=true" : ""}`;
}

/** Upload with progress (fetch cannot report upload progress). */
export function uploadDocument<T>(caseId: number, file: File, docType: string, onProgress: (pct: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/cases/${caseId}/documents`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
    xhr.onerror = () => reject(new ApiClientError(`Cannot reach the backend at ${API_BASE}. Is it running?`, 0, "network_error"));
    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) { onProgress(100); resolve(body as T); }
      else {
        if (xhr.status === 401) window.dispatchEvent(new Event("auth:expired"));
        reject(new ApiClientError(body?.error?.message ?? `Upload failed (${xhr.status}).`, xhr.status, body?.error?.code ?? "upload_failed"));
      }
    };
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    xhr.send(form);
  });
}
