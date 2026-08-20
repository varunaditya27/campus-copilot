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
  history: { role: ChatRole; content: string }[];
}

export interface ChatResponse {
  reply: string;
  sources?: Source[];
  toolActivity?: ToolActivityEntry[];
  confirmation?: RegistrationConfirmation;
}

export interface ConfirmRegistrationRequest {
  event_id: string;
  student_id: string;
}

export interface ConfirmRegistrationResponse {
  success: boolean;
  registration_id?: string;
  error?: string;
}
