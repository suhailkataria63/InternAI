import type {
  AnalysisRequest,
  AnalysisResponse,
  ApplicationDetail,
  ApplicationListItem,
  ApplicationStatus,
  ResumeUploadResponse,
} from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 60_000;

export async function analyzeApplication(
  payload: AnalysisRequest,
): Promise<AnalysisResponse> {
  return requestJson<AnalysisResponse>("/api/orchestrator/analyze-application", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadResumePdf(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    response = await fetch(`${API_BASE_URL}/api/resume/upload`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    window.clearTimeout(timeoutId);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Resume upload timed out. Try a smaller PDF or paste the resume text manually.");
    }
    throw new Error(
      `Could not reach the InternAI backend at ${API_BASE_URL}. Make sure FastAPI is running before uploading a resume.`,
    );
  }

  if (!response.ok) {
    let message = "Failed to extract resume text. Please paste resume text manually.";
    try {
      const body = await response.json();
      message = extractErrorMessage(body, message);
    } catch {
      // Keep the upload-specific fallback message when the backend does not return JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ResumeUploadResponse>;
}

export async function saveApplicationAnalysis(
  payload: AnalysisResponse,
): Promise<ApplicationDetail> {
  return requestJson<ApplicationDetail>("/api/tracker/applications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listApplications(): Promise<ApplicationListItem[]> {
  return requestJson<ApplicationListItem[]>("/api/tracker/applications");
}

export async function getApplication(id: number): Promise<ApplicationDetail> {
  return requestJson<ApplicationDetail>(`/api/tracker/applications/${id}`);
}

export async function updateApplicationStatus(
  id: number,
  status: ApplicationStatus,
): Promise<ApplicationDetail> {
  return requestJson<ApplicationDetail>(`/api/tracker/applications/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function updateApplicationNotes(
  id: number,
  notes: string,
): Promise<ApplicationDetail> {
  return requestJson<ApplicationDetail>(`/api/tracker/applications/${id}/notes`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
}

export async function deleteApplication(id: number): Promise<void> {
  await requestJson<void>(`/api/tracker/applications/${id}`, {
    method: "DELETE",
  });
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;

  try {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...init.headers,
      },
    });
    window.clearTimeout(timeoutId);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The InternAI backend took too long to respond. Please try again with shorter input.");
    }
    throw new Error(
      `Could not reach the InternAI backend at ${API_BASE_URL}. Make sure FastAPI is running.`,
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      message = extractErrorMessage(body, message);
    } catch {
      // Keep the default message when the backend does not return JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") {
    return fallback;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    return typeof message === "string" ? message : fallback;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const message = (item as { msg?: unknown }).msg;
        const location = (item as { loc?: unknown }).loc;
        const field = Array.isArray(location) ? location.slice(1).join(".") : "";
        if (typeof message !== "string") return "";
        return field ? `${field}: ${message}` : message;
      })
      .filter(Boolean);
    if (messages.length) {
      return messages.join(" ");
    }
  }

  return fallback;
}
