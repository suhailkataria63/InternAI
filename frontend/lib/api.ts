import type {
  AnalysisRequest,
  AnalysisResponse,
  ApplicationDetail,
  ApplicationListItem,
  ApplicationStatus,
  ResumeUploadResponse,
  ResumeProfile,
  JobProfile,
  MatchResult,
  SkillGapResult,
  ApplicationAnswer,
  CoverLetterResult,
  Tone,
  CoverLetterLength,
} from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 60_000;

export async function analyzeApplication(
  payload: AnalysisRequest,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  return requestJson<AnalysisResponse>("/api/orchestrator/analyze-application", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export async function analyzeResumeText(resumeText: string, signal?: AbortSignal): Promise<ResumeProfile> {
  const response = await requestJson<{ profile: ResumeProfile }>("/api/resume/analyze", {
    method: "POST", body: JSON.stringify({ resume_text: resumeText }), signal,
  });
  return response.profile;
}

export async function analyzeJobDescription(jobDescription: string, signal?: AbortSignal): Promise<JobProfile> {
  const response = await requestJson<{ job_profile: JobProfile }>("/api/jobs/analyze", {
    method: "POST", body: JSON.stringify({ job_description: jobDescription }), signal,
  });
  return response.job_profile;
}

export async function scoreResumeMatch(resumeProfile: ResumeProfile, jobProfile: JobProfile, signal?: AbortSignal): Promise<MatchResult> {
  return requestJson<MatchResult>("/api/match/score", {
    method: "POST", body: JSON.stringify({ resume_profile: resumeProfile, job_profile: jobProfile }), signal,
  });
}

export async function analyzeSkillGaps(resumeProfile: ResumeProfile, jobProfile: JobProfile, matchResult: MatchResult, signal?: AbortSignal): Promise<SkillGapResult> {
  return requestJson<SkillGapResult>("/api/skill-gap/analyze", {
    method: "POST", body: JSON.stringify({ resume_profile: resumeProfile, job_profile: jobProfile, match_result: matchResult }), signal,
  });
}

export async function writeApplicationAnswer(input: {
  resume_profile: ResumeProfile; job_profile: JobProfile; match_result: MatchResult;
  skill_gap_result: SkillGapResult; application_question: string; tone: Tone; word_limit: number;
}, signal?: AbortSignal): Promise<ApplicationAnswer> {
  return requestJson<ApplicationAnswer>("/api/application/write", {
    method: "POST", body: JSON.stringify(input), signal,
  });
}

export async function writeCoverLetter(input: {
  resume_profile: ResumeProfile; job_profile: JobProfile; match_result: MatchResult;
  skill_gap_result: SkillGapResult; tone: Tone; length: CoverLetterLength;
}, signal?: AbortSignal): Promise<CoverLetterResult> {
  return requestJson<CoverLetterResult>("/api/cover-letter/generate", {
    method: "POST", body: JSON.stringify(input), signal,
  });
}

export async function uploadResumePdf(
  file: File,
  signal?: AbortSignal,
): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });

  try {
    response = await fetch(`${API_BASE_URL}/api/resume/upload`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        signal?.aborted
          ? "Resume upload was cancelled."
          : "Resume upload timed out. Try a smaller PDF or paste the resume text manually.",
      );
    }
    throw new Error(
      `Could not reach the InternAI backend at ${API_BASE_URL}. Make sure FastAPI is running before uploading a resume.`,
    );
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
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
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const callerSignal = init.signal;
  const abortFromCaller = () => controller.abort();
  callerSignal?.addEventListener("abort", abortFromCaller, { once: true });

  try {
    const { signal: _signal, headers, ...requestInit } = init;
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...requestInit,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        callerSignal?.aborted
          ? "Request was cancelled."
          : "The InternAI backend took too long to respond. Please try again with shorter input.",
      );
    }
    throw new Error(
      `Could not reach the InternAI backend at ${API_BASE_URL}. Make sure FastAPI is running.`,
    );
  } finally {
    window.clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", abortFromCaller);
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
