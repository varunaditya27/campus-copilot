"use client";

import { useState, type KeyboardEvent } from "react";
import { ArrowRightIcon } from "../icons";

export default function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="bg-ground px-5 py-4 md:px-6">
      <div className="mx-auto flex max-w-2xl items-end gap-2 border border-muted bg-ground p-1.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ink">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask Campus Copilot…"
          disabled={disabled}
          className="max-h-32 flex-1 resize-none bg-transparent px-2 py-2 text-body leading-relaxed text-ink placeholder:text-muted focus:outline-none"
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="flex h-11 w-11 shrink-0 items-center justify-center bg-accent text-accent-ink transition-transform duration-150 active:scale-[0.95] disabled:opacity-30"
        >
          <ArrowRightIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
