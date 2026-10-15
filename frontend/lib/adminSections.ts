import type { Role } from "./types";

export interface AdminSection {
  href: string;
  label: string;
  roles: Role[];
}

// Who sees which part of the dashboard. The backend enforces the same rules.
export const ADMIN_SECTIONS: AdminSection[] = [
  { href: "/admin/events", label: "Events", roles: ["faculty", "admin"] },
  { href: "/admin/students", label: "Students", roles: ["admin"] },
  { href: "/admin/knowledge", label: "Knowledge", roles: ["admin"] },
  { href: "/admin/grievances", label: "Grievances", roles: ["staff", "admin"] },
  { href: "/admin/analytics", label: "Analytics", roles: ["admin"] },
];

export function sectionsFor(role: Role): AdminSection[] {
  return ADMIN_SECTIONS.filter((s) => s.roles.includes(role));
}
