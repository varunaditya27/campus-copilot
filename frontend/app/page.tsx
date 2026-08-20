"use client";

import { useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { sendChatMessage, ApiError } from "@/lib/api";
import ChatWindow from "./components/chat/ChatWindow";
import ChatInput from "./components/chat/ChatInput";
import AgentActivity from "./components/agent/AgentActivity";

let idCounter = 0;
function nextId() {
  idCounter += 1;
  return `msg_${idCounter}`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const allActivity = messages.flatMap((m) =>
    (m.toolActivity ?? []).map((entry) => ({ ...entry, id: `${m.id}:${entry.id}` })),
  );

  async function handleSend(text: string) {
    const userMessage: ChatMessage = {
      id: nextId(),
      role: "user",
      content: text,
    };
    const pendingId = nextId();
    const pendingMessage: ChatMessage = {
      id: pendingId,
      role: "assistant",
      content: "",
      pending: true,
    };

    setBanner(null);
    setMessages((prev) => [...prev, userMessage, pendingMessage]);
    setSending(true);

    try {
      const res = await sendChatMessage({
        message: text,
        history: messages.map((m) => ({ role: m.role, content: m.content })),
      });

      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                ...m,
                content: res.reply,
                pending: false,
                sources: res.sources,
                toolActivity: res.toolActivity,
                confirmation: res.confirmation,
              }
            : m,
        ),
      );
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== pendingId));
      setBanner(
        err instanceof ApiError
          ? err.message
          : "Something went wrong reaching Campus Copilot.",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-h-0 flex-1 flex-col">
        {banner && (
          <div className="rule-bottom border-line bg-rust/10 px-6 py-2.5">
            <p className="font-mono text-[11.5px] text-rust">{banner}</p>
          </div>
        )}
        <ChatWindow messages={messages} onSelectPrompt={handleSend} />
        <ChatInput onSend={handleSend} disabled={sending} />
      </div>
      <AgentActivity entries={allActivity} />
    </div>
  );
}
