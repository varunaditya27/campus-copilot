"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import MessageBubble from "./MessageBubble";
import SuggestedPrompts from "./SuggestedPrompts";

export default function ChatWindow({
  messages,
  onSelectPrompt,
}: {
  messages: ChatMessage[];
  onSelectPrompt: (prompt: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="thin-scroll flex flex-1 flex-col items-center justify-center overflow-y-auto px-6 py-10">
        <div className="w-full max-w-2xl">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-brass">
            Campus Copilot
          </p>
          <h1 className="mt-2 font-display text-[28px] font-medium leading-tight text-ink">
            Ask about campus policy, find an event, or get something done.
          </h1>
          <p className="mt-2 max-w-md text-[14px] leading-relaxed text-ink-soft">
            Answers are grounded in the campus knowledge base. Requests that
            require action — like registering for an event — always ask for
            your confirmation first.
          </p>
          <div className="mt-6">
            <SuggestedPrompts onSelect={onSelectPrompt} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="thin-scroll flex-1 overflow-y-auto px-6 py-8">
      <div className="mx-auto flex max-w-2xl flex-col gap-7">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
