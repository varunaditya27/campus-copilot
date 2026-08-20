import type { ChatMessage } from "@/lib/types";
import SourceCard from "../rag/SourceCard";
import ConfirmationCard from "../agent/ConfirmationCard";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`anim-rise ${isUser ? "ml-auto" : "mr-auto"} max-w-2xl`}>
      <div
        className={`mb-1 font-mono text-[10.5px] uppercase tracking-[0.16em] ${
          isUser ? "text-right text-ink-faint" : "text-brass"
        }`}
      >
        {isUser ? "You" : "Campus Copilot"}
      </div>

      {message.pending ? (
        <div className="flex items-center gap-1.5 py-1">
          <span className="h-1.5 w-1.5 animate-pulse bg-ink-faint" />
          <span className="h-1.5 w-1.5 animate-pulse bg-ink-faint [animation-delay:150ms]" />
          <span className="h-1.5 w-1.5 animate-pulse bg-ink-faint [animation-delay:300ms]" />
        </div>
      ) : (
        <p
          className={`whitespace-pre-wrap text-[15px] leading-relaxed ${
            isUser ? "text-right text-ink" : "text-ink"
          }`}
        >
          {message.content}
        </p>
      )}

      {message.sources && message.sources.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {message.sources.map((s, i) => (
            <SourceCard key={`${s.document}-${i}`} source={s} />
          ))}
        </div>
      )}

      {message.confirmation && (
        <div className="mt-3">
          <ConfirmationCard confirmation={message.confirmation} />
        </div>
      )}
    </div>
  );
}
