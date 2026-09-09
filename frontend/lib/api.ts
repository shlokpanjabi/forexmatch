import type { ApiError, Recommendation, StreamEvent } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiRequestError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "ApiRequestError";
  }
}

/** The API could not be reached at all — as opposed to answering with an error. */
export class ApiUnreachableError extends Error {
  constructor(public readonly baseUrl: string) {
    super(`Could not reach the ForexMatch API at ${baseUrl}`);
    this.name = "ApiUnreachableError";
  }
}

async function parseError(response: Response): Promise<never> {
  let code = "REQUEST_FAILED";
  let message = "Something went wrong. Please try again.";
  try {
    const body = (await response.json()) as ApiError;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    // A non-JSON error body tells us nothing useful; keep the generic message.
  }
  throw new ApiRequestError(code, message);
}

/**
 * Stream a chat turn.
 *
 * Uses fetch rather than EventSource because the request is a POST, and because
 * we want tool events to surface the moment the backend emits them.
 */
export async function* streamChat(
  message: string,
  sessionId: string | null,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    });
  } catch (caught) {
    // A failed fetch means DNS, connection refused, CORS or mixed content —
    // the request never reached the API. That is a different problem from the
    // API rejecting it, and deserves a different message.
    if ((caught as Error)?.name === "AbortError") throw caught;
    throw new ApiUnreachableError(API_BASE);
  }

  if (!response.ok) await parseError(response);
  if (!response.body) throw new ApiRequestError("NO_STREAM", "The server sent no response body.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        yield JSON.parse(line.slice(6)) as StreamEvent;
      } catch {
        // A truncated frame is not worth failing the whole stream over.
      }
    }
  }
}

export async function fetchRecommendation(
  profile: unknown,
  sessionId: string | null,
): Promise<Recommendation> {
  const response = await fetch(`${API_BASE}/api/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile, session_id: sessionId }),
  });
  if (!response.ok) await parseError(response);
  return (await response.json()) as Recommendation;
}

/** Records the click server-side, then returns the URL to open. */
export async function resolveApplicationUrl(
  slug: string,
  sessionId: string,
  source = "recommendation",
): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE}/api/application-click`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, session_id: sessionId, source }),
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { application_url: string | null };
    return body.application_url;
  } catch {
    return null;
  }
}
