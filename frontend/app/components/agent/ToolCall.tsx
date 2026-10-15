import type { ToolActivityEntry } from "@/lib/types";
import {
  CheckIcon,
  SearchIcon,
  AlertIcon,
  SpinIcon,
  DotIcon,
  UserIcon,
  DocumentIcon,
} from "../icons";

const TOOL_ICON: Record<ToolActivityEntry["tool"], (p: { className?: string }) => React.JSX.Element> = {
  search_events: SearchIcon,
  check_event_availability: DotIcon,
  register_for_event: CheckIcon,
  calculate_attendance: DotIcon,
  get_attendance_report: UserIcon,
  get_cgpa: DocumentIcon,
  get_student_timetable: DotIcon,
  get_exam_schedule: DocumentIcon,
  get_elective_options: SearchIcon,
  get_fee_dues: DocumentIcon,
  get_course_info: SearchIcon,
  get_faculty_profile: UserIcon,
  check_library_availability: SearchIcon,
  get_canteen_menu: DocumentIcon,
  get_bus_schedule: DotIcon,
  get_lost_and_found: SearchIcon,
  check_study_room_availability: SearchIcon,
  get_grievance_status: DocumentIcon,
  get_counselling_slots: DotIcon,
  get_placement_drives: DocumentIcon,
  check_placement_eligibility: CheckIcon,
  reserve_library_book: CheckIcon,
  book_study_room: CheckIcon,
  report_maintenance_issue: CheckIcon,
  submit_lost_item: CheckIcon,
  create_grievance_ticket: CheckIcon,
  book_counselling_appointment: CheckIcon,
  get_event_detail: SearchIcon,
  get_my_registrations: DocumentIcon,
  get_event_feedback_form: DocumentIcon,
  cancel_event_registration: CheckIcon,
  join_event_waitlist: CheckIcon,
  submit_event_feedback: CheckIcon,
};

export default function ToolCall({
  entry,
  index,
  isLast,
}: {
  entry: ToolActivityEntry;
  index: number;
  isLast: boolean;
}) {
  const Icon = TOOL_ICON[entry.tool];

  return (
    <div className="anim-rise relative flex gap-3 pb-5" style={{ animationDelay: `${index * 70}ms` }}>
      {!isLast && (
        <span className="absolute left-[9px] top-5 bottom-0 w-px bg-line" aria-hidden />
      )}
      <span
        className={`z-10 mt-0.5 flex h-[19px] w-[19px] shrink-0 items-center justify-center border ${
          entry.status === "error"
            ? "border-rust text-rust bg-cream"
            : entry.status === "running"
              ? "border-brass text-brass bg-cream"
              : "border-forest text-forest bg-cream"
        }`}
      >
        {entry.status === "running" ? (
          <SpinIcon className="h-3 w-3" />
        ) : entry.status === "error" ? (
          <AlertIcon className="h-3 w-3" />
        ) : (
          <Icon className="h-3 w-3" />
        )}
      </span>

      <div className="min-w-0 pt-px">
        <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-soft">
          {entry.label}
        </p>
        {entry.resultSummary && (
          <p className="mt-0.5 text-[13px] leading-snug text-ink">
            {entry.resultSummary}
          </p>
        )}
      </div>
    </div>
  );
}
