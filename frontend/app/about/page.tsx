const STAGES = [
  {
    label: "Chatbot",
    line: "Generates a response.",
  },
  {
    label: "RAG Assistant",
    line: "Answers using the campus knowledge base, with sources.",
  },
  {
    label: "Tool-Using AI",
    line: "Calls deterministic software functions and reads their results.",
  },
  {
    label: "Agent",
    line: "Decides which information and actions a goal requires — then does it.",
  },
];

export default function AboutPage() {
  return (
    <div className="thin-scroll flex-1 overflow-y-auto px-6 py-10">
      <div className="mx-auto max-w-2xl">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-brass">
          About
        </p>
        <h1 className="mt-2 font-display text-3xl font-medium leading-tight text-ink">
          A campus assistant that can actually get things done.
        </h1>
        <p className="mt-4 text-[14.5px] leading-relaxed text-ink-soft">
          Campus Copilot answers questions using a curated campus knowledge
          base, checks real event data through deterministic tools, and —
          only with your explicit confirmation — takes action on your
          behalf, such as registering you for an event.
        </p>

        <div className="mt-10 border border-line bg-cream-raised">
          {STAGES.map((stage, i) => (
            <div
              key={stage.label}
              className={`flex gap-4 px-5 py-4 ${
                i !== STAGES.length - 1 ? "rule-bottom border-line" : ""
              }`}
            >
              <span className="w-6 shrink-0 font-mono text-[12px] text-ink-faint">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="font-display text-[16px] font-medium text-ink">
                  {stage.label}
                </p>
                <p className="mt-0.5 text-[13.5px] leading-relaxed text-ink-soft">
                  {stage.line}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-10">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
            Built with
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {[
              "Next.js",
              "FastAPI",
              "Groq",
              "ChromaDB",
              "JSON data",
            ].map((tech) => (
              <span
                key={tech}
                className="border border-line px-2.5 py-1 font-mono text-[11px] text-ink-soft"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>

        <p className="mt-10 border-t border-line pt-6 text-[13px] leading-relaxed text-ink-faint">
          Consequential actions always require human confirmation. The
          agent may reason and plan autonomously, but it never registers
          you for anything without asking first.
        </p>
      </div>
    </div>
  );
}
