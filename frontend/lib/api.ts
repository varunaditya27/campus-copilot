import type {
  AgentEvent,
  CampusEvent,
  ChatHistoryResponse,
  ChatRequest,
  ConfirmRegistrationRequest,
  ConfirmRegistrationResponse,
  CurrentStudent,
  LoginRequest,
  RegisterAccountRequest,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const UNREACHABLE_MESSAGE =
  "Could not reach the Campus Copilot backend. Is the FastAPI server running?";

class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

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

// Called when the user's session has ended and cannot be renewed.
let sessionExpiredListener: (() => void) | null = null;

export function onSessionExpired(listener: (() => void) | null) {
  sessionExpiredListener = listener;
}

// Sign-in itself and the refresh call must not trigger another refresh.
const NO_REFRESH_PATHS = [
  "/api/auth/login",
  "/api/auth/register",
  "/api/auth/refresh",
  "/api/auth/logout",
];

// The refresh token works once, so concurrent 401s share a single refresh.
let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  })
    .then(
      (res) => res.ok,
      () => false,
    )
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

// fetch with the session cookies attached. A 401 on a protected call means the
// short-lived access token expired: renew it once and retry.
async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const attempt = async () => {
    try {
      return await fetch(`${API_BASE_URL}${path}`, {
        credentials: "include",
        ...init,
      });
    } catch {
      throw new ApiError(UNREACHABLE_MESSAGE);
    }
  };

  const res = await attempt();
  if (res.status !== 401 || NO_REFRESH_PATHS.includes(path)) {
    return res;
  }
  if (!(await refreshSession())) {
    sessionExpiredListener?.();
    return res;
  }
  const retried = await attempt();
  if (retried.status === 401) {
    sessionExpiredListener?.();
  }
  return retried;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await send(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw await toApiError(path, res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// Send a chat message and call onEvent for each server-sent event as it
// arrives. EventSource only supports GET, so the stream is read with fetch.
export async function streamChatMessage(
  body: ChatRequest,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const path = "/api/chat/stream";
  const res = await send(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

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
  return post<ConfirmRegistrationResponse>("/api/register", body);
}

export function listEvents(): Promise<CampusEvent[]> {
  return request<CampusEvent[]>("/api/events");
}

export function getEvent(id: string): Promise<CampusEvent> {
  return request<CampusEvent>(`/api/events/${id}`);
}

export function getCurrentStudent(): Promise<CurrentStudent> {
  return request<CurrentStudent>("/api/auth/me");
}

export function login(body: LoginRequest): Promise<CurrentStudent> {
  return post<CurrentStudent>("/api/auth/login", body);
}

export function registerAccount(
  body: RegisterAccountRequest,
): Promise<CurrentStudent> {
  return post<CurrentStudent>("/api/auth/register", body);
}

export function logout(): Promise<void> {
  return post<void>("/api/auth/logout");
}

export { ApiError };
