import type { AnalysisRequest, AnalysisResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function analyzeApplication(
  payload: AnalysisRequest,
): Promise<AnalysisResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/orchestrator/analyze-application`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      `Could not reach the InternAI backend at ${API_BASE_URL}. Make sure FastAPI is running.`,
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail?.message) {
        message = body.detail.message;
      }
    } catch {
      // Keep the default message when the backend does not return JSON.
    }
    throw new Error(message);
  }

  return response.json();
}
