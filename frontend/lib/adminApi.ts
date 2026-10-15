import { ApiError, post, request, send, toApiError } from "./api";
import type {
  Analytics,
  DocumentChunks,
  EventInput,
  EventRoster,
  Grievance,
  GrievanceList,
  GrievanceStatus,
  ImportResult,
  IngestReport,
  KnowledgeStatus,
  StudentDetail,
  StudentPage,
} from "./adminTypes";
import type { CampusEvent } from "./types";

function query(params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

// Multipart uploads must not set Content-Type: the browser adds the boundary.
async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const res = await send(path, { method: "POST", body });
  if (!res.ok) throw await toApiError(path, res);
  return res.json() as Promise<T>;
}

// --- events

export function createEvent(input: EventInput): Promise<CampusEvent> {
  return post<CampusEvent>("/api/admin/events", input);
}

export function updateEvent(
  id: string,
  input: EventInput,
): Promise<CampusEvent> {
  return request<CampusEvent>(`/api/admin/events/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteEvent(
  id: string,
  force = false,
): Promise<{ id: string; registrations_removed: number }> {
  return request(`/api/admin/events/${id}${query({ force: force ? "true" : undefined })}`, {
    method: "DELETE",
  });
}

export function getEventRoster(id: string): Promise<EventRoster> {
  return request<EventRoster>(`/api/admin/events/${id}/registrations`);
}

export async function exportRegistrations(id: string): Promise<Blob> {
  const path = `/api/admin/events/${id}/registrations/export`;
  const res = await send(path, { method: "POST" });
  if (!res.ok) throw await toApiError(path, res);
  return res.blob();
}

// --- students

export function listStudents(params: {
  page: number;
  q?: string;
  program?: string;
  year?: string;
}): Promise<StudentPage> {
  return request<StudentPage>(`/api/admin/students${query({ ...params, page_size: 15 })}`);
}

export function getStudent(id: string): Promise<StudentDetail> {
  return request<StudentDetail>(`/api/admin/students/${encodeURIComponent(id)}`);
}

export function importStudents(file: File): Promise<ImportResult> {
  return upload<ImportResult>("/api/admin/students/import", file);
}

// --- knowledge

export function getKnowledgeStatus(): Promise<KnowledgeStatus> {
  return request<KnowledgeStatus>("/api/admin/knowledge/status");
}

export function runIngest(full: boolean): Promise<IngestReport> {
  return post<IngestReport>(`/api/admin/knowledge/ingest${query({ full: full ? "true" : undefined })}`);
}

export function uploadDocument(file: File): Promise<{ document: string; chunks: number; replaced: boolean }> {
  return upload("/api/admin/knowledge/upload", file);
}

export function deleteDocument(name: string): Promise<{ document: string; chunks_removed: number }> {
  return request(`/api/admin/knowledge/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export function getDocumentChunks(name: string): Promise<DocumentChunks> {
  return request<DocumentChunks>(`/api/admin/knowledge/${encodeURIComponent(name)}/chunks`);
}

// --- grievances

export function listGrievances(): Promise<GrievanceList> {
  return request<GrievanceList>("/api/admin/grievances");
}

export function updateGrievance(
  id: number,
  status: GrievanceStatus,
  resolutionNote: string | null,
): Promise<Grievance> {
  return request<Grievance>(`/api/admin/grievances/${id}`, {
    method: "PUT",
    body: JSON.stringify({ status, resolution_note: resolutionNote }),
  });
}

// --- analytics

export function getAnalytics(days: number): Promise<Analytics> {
  return request<Analytics>(`/api/admin/analytics${query({ days })}`);
}

export { ApiError };
