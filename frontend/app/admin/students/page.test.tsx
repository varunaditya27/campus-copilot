import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import type { StudentPage } from "@/lib/adminTypes";
import AdminStudentsPage from "./page";

const mocks = vi.hoisted(() => ({ listStudents: vi.fn(), importStudents: vi.fn() }));
vi.mock("@/lib/adminApi", () => mocks);

const page = (over: Partial<StudentPage> = {}): StudentPage => ({
  items: [{ student_id: "1RV23IS101", name: "Aarav Sharma", program: "ISE", year: 3, has_account: true }],
  page: 1, page_size: 15, total: 1, programs: ["CSE", "ISE"], ...over,
});

beforeEach(() => {
  mocks.listStudents.mockReset().mockResolvedValue(page());
  mocks.importStudents.mockReset();
});

describe("the students page", () => {
  it("lists the roster with a link to each student", async () => {
    render(<AdminStudentsPage />);
    expect(await screen.findByRole("link", { name: "Aarav Sharma" })).toHaveAttribute("href", "/admin/students/1RV23IS101");
    expect(screen.getByText("Signed up")).toBeInTheDocument();
    expect(screen.getByText(/1 students · page 1 of 1/)).toBeInTheDocument();
  });

  it("waits for a pause in typing before searching", async () => {
    render(<AdminStudentsPage />);
    await screen.findByRole("link", { name: "Aarav Sharma" });
    mocks.listStudents.mockClear();
    await userEvent.type(screen.getByLabelText("Search students"), "aar");
    expect(mocks.listStudents).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.listStudents).toHaveBeenCalledTimes(1), { timeout: 2000 });
    expect(mocks.listStudents).toHaveBeenLastCalledWith(expect.objectContaining({ q: "aar", page: 1 }));
  });

  it("filters by programme and year and goes back to the first page", async () => {
    mocks.listStudents.mockResolvedValue(page({ total: 40, page: 1 }));
    render(<AdminStudentsPage />);
    await screen.findByRole("link", { name: "Aarav Sharma" });
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(mocks.listStudents).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
    await userEvent.selectOptions(screen.getByLabelText("Filter by year"), "4");
    await waitFor(() => expect(mocks.listStudents).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, year: "4" })));
    await userEvent.selectOptions(screen.getByLabelText("Filter by programme"), "CSE");
    await waitFor(() => expect(mocks.listStudents).toHaveBeenLastCalledWith(expect.objectContaining({ program: "CSE" })));
  });

  it("disables Previous on the first page and Next on the last", async () => {
    mocks.listStudents.mockResolvedValue(page({ total: 40 }));
    render(<AdminStudentsPage />);
    await screen.findByText(/page 1 of 3/);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("reports an import and refreshes the list", async () => {
    mocks.importStudents.mockResolvedValue({ created: 2, skipped_existing: ["1RV23IS101"] });
    render(<AdminStudentsPage />);
    await screen.findByRole("link", { name: "Aarav Sharma" });
    mocks.listStudents.mockClear();
    const file = new File(["student_id,name,program,year\n"], "students.csv", { type: "text/csv" });
    await act(async () => {
      await userEvent.upload(screen.getByLabelText("CSV file to import"), file);
    });
    expect(await screen.findByText(/Added 2 students/)).toHaveTextContent("1RV23IS101");
    expect(mocks.importStudents).toHaveBeenCalledWith(file);
    await waitFor(() => expect(mocks.listStudents).toHaveBeenCalled());
  });

  it("shows why an import was refused", async () => {
    mocks.importStudents.mockRejectedValue(new ApiError("1 problems found, nothing was imported. First: line 2: year must be 1, 2, 3 or 4."));
    render(<AdminStudentsPage />);
    await screen.findByRole("link", { name: "Aarav Sharma" });
    await userEvent.upload(screen.getByLabelText("CSV file to import"), new File(["x"], "bad.csv"));
    expect(await screen.findByRole("alert")).toHaveTextContent("nothing was imported");
  });
});
