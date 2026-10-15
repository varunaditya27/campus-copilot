"use client";

import { useEffect, useState } from "react";
import type { ChatMessage, StoredMessage } from "@/lib/types";
import { getChatHistory, streamChatMessage, ApiError } from "@/lib/api";
import { applyAgentEvent } from "@/lib/events";
import ChatWindow from "./components/chat/ChatWindow";
import ChatInput from "./components/chat/ChatInput";
import AgentActivity from "./components/agent/AgentActivity";
import RequireAuth from "./components/auth/RequireAuth";

let idCounter = 0;
function nextId() {
  idCounter += 1;
  return `msg_${idCounter}`;
}

function toChatMessage(m: StoredMessage): ChatMessage {
  return {
    id: `stored_${m.id}`,
    role: m.role,
    content: m.content,
    sources: m.sources ?? undefined,
    toolActivity: m.toolActivity ?? undefined,
  };
}

export default function ChatPage() {
  return (
    <RequireAuth>
      <Chat />
    </RequireAuth>
  );
}

function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getChatHistory()
      .then(({ messages: stored }) => {
        // Don't overwrite a message the user already sent while this loaded.
        if (!cancelled) {
          setMessages((prev) => (prev.length > 0 ? prev : stored.map(toChatMessage)));
        }
      })
      .catch(() => {
        // Restoring history is a convenience; start with an empty chat if it fails.
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
      let failure: string | null = null;
      let finished = false;

      await streamChatMessage({ message: text }, (event) => {
        if (event.type === "error") {
          failure = event.payload.message;
        } else if (event.type === "done") {
          finished = true;
        }
        setMessages((prev) =>
          prev.map((m) => (m.id === pendingId ? applyAgentEvent(m, event) : m)),
        );
      });

      if (failure || !finished) {
        setMessages((prev) => prev.filter((m) => m.id !== pendingId));
        setBanner(failure ?? "The response was interrupted. Please try again.");
      }
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
