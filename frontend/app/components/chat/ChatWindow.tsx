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
          <h1 className="text-lead font-medium text-balance text-ink">
            Ask about campus policy, find an event, or get something done.
          </h1>
          <p className="mt-3 max-w-[60ch] text-body text-ink">
            Answers come from the campus handbook. Anything that changes something, like
            registering for an event, asks you to confirm first.
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
