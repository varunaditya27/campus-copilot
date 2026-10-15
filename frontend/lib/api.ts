import type {
  CampusEvent,
  ChatHistoryResponse,
  ChatRequest,
  ChatResponse,
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
    throw new ApiError(
      "Could not reach the Campus Copilot backend. Is the FastAPI server running?",
    );
  }

  if (!res.ok) {
    let message = `Request to ${path} failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.message === "string") {
        message = body.message;
      }
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiError(message, res.status);
  }

  return res.json() as Promise<T>;
}

export function sendChatMessage(body: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
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
