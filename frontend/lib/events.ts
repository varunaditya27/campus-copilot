import type { AgentEvent, ChatMessage, ToolActivityEntry } from "./types";

// Fold one streamed event into the assistant message it belongs to.
// "pending" keeps the thinking skeleton visible until text starts arriving.
export function applyAgentEvent(message: ChatMessage, event: AgentEvent): ChatMessage {
  switch (event.type) {
    case "rag_context":
      return { ...message, sources: event.payload.sources };

    case "tool_start": {
      const running: ToolActivityEntry = { ...event.payload, status: "running" };
      return { ...message, toolActivity: [...(message.toolActivity ?? []), running] };
    }

    case "tool_done": {
      const entries = message.toolActivity ?? [];
      const known = entries.some((e) => e.id === event.payload.id);
      return {
        ...message,
        toolActivity: known
          ? entries.map((e) => (e.id === event.payload.id ? event.payload : e))
          : [...entries, event.payload],
      };
    }

    case "reset":
      return { ...message, content: "", pending: true };

    case "token":
      return { ...message, content: message.content + event.payload.text, pending: false };

    case "done":
      return {
        ...message,
        content: event.payload.reply,
        pending: false,
        sources: event.payload.sources ?? undefined,
        toolActivity: event.payload.toolActivity ?? undefined,
        confirmation: event.payload.confirmation ?? undefined,
      };

    case "error":
      return message;
  }
}
