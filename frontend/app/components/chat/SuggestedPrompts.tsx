const PROMPTS = [
  "Where is the library?",
  "What happens if my attendance falls below the required percentage?",
  "What technical events are happening this week?",
  "Find an AI-related event tomorrow and register me.",
];

export default function SuggestedPrompts({
  onSelect,
}: {
  onSelect: (prompt: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onSelect(prompt)}
          className="group border border-line bg-cream-raised px-3.5 py-3 text-left transition-colors duration-150 hover:border-brass-line hover:bg-cream"
        >
          <span className="text-[13.5px] leading-snug text-ink-soft group-hover:text-ink">
            {prompt}
          </span>
        </button>
      ))}
    </div>
  );
}
