import type {
  CampusEvent,
  AgentEvent,
  ChatHistoryResponse,
  ChatRequest,
  ConfirmRegistrationRequest,
  ConfirmRegistrationResponse,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const UNREACHABLE_MESSAGE =
  "Could not reach the Campus Copilot backend. Is the FastAPI server running?";

// Build an ApiError from a failed response, preferring the backend's message.
async function toApiError(path: string, res: Response): Promise<ApiError> {
  let message = `Request to ${path} failed (${res.status})`;
  try {
    const body = await res.json();
    if (typeof body?.message === "string") {
      message = body.message;
    }
  } catch {
    // Non-JSON error body: keep the generic message.
  }
  return new ApiError(message, res.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      // The backend identifies a conversation by an HttpOnly session cookie.
      credentials: "include",
      ...init,
    });
  } catch {
    throw new ApiError(UNREACHABLE_MESSAGE);
  }

  if (!res.ok) {
    throw await toApiError(path, res);
  }

  return res.json() as Promise<T>;
}

// Send a chat message and call onEvent for each server-sent event as it
// arrives. EventSource only supports GET, so the stream is read with fetch.
export async function streamChatMessage(
  body: ChatRequest,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const path = "/api/chat/stream";
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(UNREACHABLE_MESSAGE);
  }

  if (!res.ok || !res.body) {
    throw await toApiError(path, res);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    // Events are separated by a blank line; a read may end mid-event.
    buffer += value;
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice("data: ".length))
        .join("\n");
      if (data) {
        onEvent(JSON.parse(data) as AgentEvent);
      }
    }
  }
}

export function getChatHistory(): Promise<ChatHistoryResponse> {
  return request<ChatHistoryResponse>("/api/chat/history");
}

export function confirmRegistration(
  body: ConfirmRegistrationRequest,
): Promise<ConfirmRegistrationResponse> {
  return request<ConfirmRegistrationResponse>("/api/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listEvents(): Promise<CampusEvent[]> {
  return request<CampusEvent[]>("/api/events");
}

export function getEvent(id: string): Promise<CampusEvent> {
  return request<CampusEvent>(`/api/events/${id}`);
}

export { ApiError };
