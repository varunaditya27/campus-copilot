import { describe, expect, it } from "vitest";
import { ADMIN_SECTIONS, sectionsFor } from "./adminSections";

describe("which dashboard sections each role sees", () => {
  it("shows administrators everything", () => {
    expect(sectionsFor("admin").map((s) => s.label)).toEqual(["Events", "Students", "Knowledge", "Grievances", "Analytics"]);
  });

  it("shows faculty only events", () => {
    expect(sectionsFor("faculty").map((s) => s.label)).toEqual(["Events"]);
  });

  it("shows staff only grievances", () => {
    expect(sectionsFor("staff").map((s) => s.label)).toEqual(["Grievances"]);
  });

  it("shows students nothing", () => {
    expect(sectionsFor("student")).toEqual([]);
  });

  it("gives every section a unique address under /admin", () => {
    const hrefs = ADMIN_SECTIONS.map((s) => s.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(hrefs.every((h) => h.startsWith("/admin/"))).toBe(true);
  });
});
