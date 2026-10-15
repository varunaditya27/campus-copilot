import type { CampusEvent, EventCategory } from "./types";

export interface EventInput {
  name: string;
  category: EventCategory;
  date: string;
  time: string;
  duration_minutes: number;
  venue: string;
  capacity: number;
  organizer: string;
  description: string;
  tags: string[];
  department: string | null;
}

export interface RegistrationRecord {
  registration_id: string;
  status: string;
  registered_at: string;
  event_id: string;
  event_name: string;
  event_date: string;
  student_id: string;
  student_name: string;
  program: string;
  year: number;
}

export interface WaitlistEntry {
  position: number;
  student_id: string;
  student_name: string;
  program: string;
  year: number;
}

export interface EventRoster {
  event: CampusEvent;
  registrations: RegistrationRecord[];
  waitlist: WaitlistEntry[];
}

export interface StudentRow {
  student_id: string;
  name: string;
  program: string;
  year: number;
  has_account: boolean;
}

export interface StudentPage {
  items: StudentRow[];
  page: number;
  page_size: number;
  total: number;
  programs: string[];
}

export interface StudentDetail {
  student_id: string;
  name: string;
  program: string;
  year: number;
  semester: number;
  section: string | null;
  interests: string[];
  account: { email: string; active: boolean } | null;
  cgpa: number | null;
  backlogs: { course_code: string; name: string; semester: number }[];
  records: {
    semester: number;
    course_code: string;
    course: string;
    credits: number;
    attended: number;
    total: number;
    grade: string | null;
  }[];
  registrations: {
    registration_id: string;
    event_id: string;
    event: string;
    date: string;
    status: string;
  }[];
  tickets: { ticket: string; category: string; status: string; submitted: string }[];
}

export interface ImportResult {
  created: number;
  skipped_existing: string[];
}

export interface KnowledgeDocument {
  document: string;
  chunks: number;
  ingested_at: string | null;
  source: "curated" | "uploaded";
}

export interface KnowledgeStatus {
  collection: string;
  built: boolean;
  document_count: number;
  chunk_count: number;
  last_ingested_at: string | null;
  documents: KnowledgeDocument[];
}

export interface IngestReport {
  [key: string]: unknown;
}

export interface DocumentChunks {
  document: string;
  source: "curated" | "uploaded";
  ingested_at: string | null;
  chunk_count: number;
  embedding: { model: string; dimensions: number; collection: string };
  chunks: {
    id: string;
    section: string;
    characters: number;
    words: number;
    text: string;
  }[];
}

export type GrievanceStatus = "open" | "in_progress" | "resolved";

export interface Grievance {
  id: number;
  ticket: string;
  student_id: string;
  student_name: string;
  program: string;
  category: string;
  description: string;
  status: GrievanceStatus;
  resolution_note: string | null;
  submitted: string;
  updated: string;
}

export interface GrievanceList {
  tickets: Grievance[];
  counts: Record<GrievanceStatus, number>;
}

export interface Analytics {
  window_days: number;
  from: string;
  to: string;
  totals: { questions: number; sessions: number; active_students: number };
  daily_active_users: { date: string; users: number; questions: number }[];
  messages_per_session: {
    average: number | null;
    buckets: { label: string; sessions: number }[];
  };
  tool_usage: { tool: string; count: number; errors: number }[];
  top_documents: { document: string; count: number }[];
  top_terms: { term: string; count: number }[];
  agent: {
    replies: number;
    replies_with_tools: number;
    tool_calls: number;
    avg_tool_calls_per_reply: number | null;
    actions: {
      proposed: number;
      confirmed: number;
      cancelled: number;
      failed: number;
      expired: number;
      waiting: number;
      accept_rate: number | null;
      decided: number;
    };
  };
  rag: {
    replies: number;
    zero_context_replies: number;
    zero_context_rate: number | null;
    average_distance: number | null;
    cache_hit_rate: number | null;
    notes: string;
  };
}
