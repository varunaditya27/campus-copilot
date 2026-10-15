// Shared types for the Campus Copilot frontend.
// These mirror the JSON contracts the FastAPI backend (see ABOUT.md) is
// expected to implement.

export type EventCategory =
  | "artificial-intelligence"
  | "web-development"
  | "competitive-programming"
  | "cybersecurity"
  | "research"
  | "robotics";

export interface CampusEvent {
  id: string;
  name: string;
  category: EventCategory;
  date: string; // YYYY-MM-DD
  time: string; // HH:MM, 24h
  duration_minutes: number;
  venue: string;
  capacity: number;
  registered: number;
  organizer: string;
  description: string;
  tags: string[];
}

export interface Source {
  document: string; // e.g. "library.md"
  section?: string;
  snippet?: string;
}

export type ToolName =
  | "search_events"
  | "check_event_availability"
  | "register_for_event"
  | "calculate_attendance";

export type ToolStatus = "running" | "done" | "error";

export interface ToolActivityEntry {
  id: string;
  tool: ToolName;
  label: string; // human-readable description, e.g. "Searching campus events"
  status: ToolStatus;
  resultSummary?: string; // e.g. "Found 3 matching events"
}

export interface RegistrationConfirmation {
  event: Pick<CampusEvent, "id" | "name" | "date" | "time" | "venue">;
  studentId: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  sources?: Source[];
  toolActivity?: ToolActivityEntry[];
  confirmation?: RegistrationConfirmation;
  pending?: boolean;
}

export interface ChatRequest {
  message: string;
}

export interface StoredMessage {
  id: number;
  role: ChatRole;
  content: string;
  toolActivity: ToolActivityEntry[] | null;
  sources: Source[] | null;
  createdAt: string; // ISO 8601
}

export interface ChatHistoryResponse {
  session_id: string | null;
  messages: StoredMessage[];
}

// The backend sends null (not a missing key) for parts a reply does not have.
export interface ChatResponse {
  reply: string;
  sources?: Source[] | null;
  toolActivity?: ToolActivityEntry[] | null;
  confirmation?: RegistrationConfirmation | null;
}

// One server-sent event from POST /api/chat/stream.
export type AgentEvent =
  | { type: "rag_context"; payload: { sources: Source[] } }
  | { type: "tool_start"; payload: { id: string; tool: ToolName; label: string } }
  | { type: "tool_done"; payload: ToolActivityEntry }
  // The text streamed so far was a preamble to a tool call: discard it.
  | { type: "reset"; payload: Record<string, never> }
  | { type: "token"; payload: { text: string } }
  | { type: "done"; payload: ChatResponse }
  | { type: "error"; payload: { error_code: string; message: string } };

export interface ConfirmRegistrationRequest {
  event_id: string;
  student_id: string;
}

export interface ConfirmRegistrationResponse {
  success: boolean;
  registration_id?: string;
  error?: string;
}
