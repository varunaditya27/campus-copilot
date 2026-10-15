import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BarList, Donut, LineChart, StackedBar, WordCloud } from "./Charts";

describe("the daily active users line", () => {
  const points = [
    { date: "2026-10-13", users: 0, questions: 0 },
    { date: "2026-10-14", users: 4, questions: 9 },
    { date: "2026-10-15", users: 2, questions: 3 },
  ];

  it("draws a point for each day with a description of its values", () => {
    const { container } = render(<LineChart points={points} />);
    expect(container.querySelectorAll("circle")).toHaveLength(3);
    expect(container.querySelector("title")!.textContent).toBe("2026-10-13: 0 students, 0 questions");
    expect(screen.getByRole("img", { name: "Active students per day" })).toBeInTheDocument();
  });

  it("copes with a single day and with no activity at all", () => {
    expect(render(<LineChart points={points.slice(0, 1)} />).container.querySelectorAll("circle")).toHaveLength(1);
    expect(render(<LineChart points={points.map((p) => ({ ...p, users: 0 }))} />).container.querySelectorAll("circle")).toHaveLength(3);
  });
});

describe("the tool usage ring", () => {
  it("lists each tool with its share of the calls", () => {
    render(<Donut slices={[{ label: "get_cgpa", value: 3 }, { label: "get_fee_dues", value: 1 }]} />);
    expect(screen.getByText("get_cgpa")).toBeInTheDocument();
    expect(screen.getByText("3 (75%)")).toBeInTheDocument();
    expect(screen.getByText("1 (25%)")).toBeInTheDocument();
  });

  it("shows the total in the middle and survives having no data", () => {
    const { container } = render(<Donut slices={[]} />);
    expect(container.querySelector("text")!.textContent).toBe("0");
    expect(container.querySelectorAll("circle[stroke-dasharray]")).toHaveLength(0);
  });
});

describe("the other charts", () => {
  it("scales bars to the largest value", () => {
    const { container } = render(<BarList rows={[{ label: "a", value: 10 }, { label: "b", value: 5 }]} />);
    const widths = [...container.querySelectorAll<HTMLElement>("li > div > div")].map((d) => d.style.width);
    expect(widths).toEqual(["100%", "50%"]);
  });

  it("sizes words by how often they were used, listing them alphabetically", () => {
    render(<WordCloud terms={[{ term: "library", count: 10 }, { term: "hostel", count: 2 }, { term: "bus", count: 2 }]} />);
    const words = screen.getAllByRole("listitem");
    expect(words.map((w) => w.textContent)).toEqual(["bus", "hostel", "library"]);
    const size = (el: HTMLElement) => parseFloat(el.style.fontSize);
    expect(size(words[2])).toBeGreaterThan(size(words[1]));
    expect(size(words[0])).toBe(size(words[1]));
    expect(words[2]).toHaveAttribute("title", "10 questions");
  });

  it("splits the outcome bar in proportion and lists each part", () => {
    const { container } = render(<StackedBar parts={[{ label: "Confirmed", value: 3, colour: "#0a0" }, { label: "Cancelled", value: 1, colour: "#a00" }]} />);
    const widths = [...container.querySelectorAll<HTMLElement>("[role=img] > div")].map((d) => d.style.width);
    expect(widths).toEqual(["75%", "25%"]);
    expect(screen.getByText("Confirmed 3")).toBeInTheDocument();
  });

  it("draws an empty bar when nothing was proposed", () => {
    const { container } = render(<StackedBar parts={[{ label: "Confirmed", value: 0, colour: "#0a0" }]} />);
    expect((container.querySelector("[role=img] > div") as HTMLElement).style.width).toBe("0%");
  });
});
