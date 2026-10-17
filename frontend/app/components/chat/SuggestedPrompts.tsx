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
    <div className="flex flex-wrap gap-2">
      {PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onSelect(prompt)}
          className="bg-surface px-4 py-3 text-left text-body text-ink transition-colors duration-150 hover:bg-ink hover:text-ground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink active:scale-[0.98]"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
