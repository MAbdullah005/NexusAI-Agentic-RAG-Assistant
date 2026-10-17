"use client";

import React, { useState, useRef, useEffect } from "react";
import { ArrowUp, Paperclip, Sparkles, FileText, Youtube, Globe } from "lucide-react";
import { Button } from "../ui/button";

interface ChatComposerProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  onOpenSourceModal?: () => void;
  placeholder?: string;
}

export function ChatComposer({
  onSendMessage,
  disabled = false,
  onOpenSourceModal,
  placeholder = "Ask a question about your documents, YouTube videos, or web sources...",
}: ChatComposerProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSendMessage(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto p-4">
      <div className="relative rounded-2xl border border-zinc-800/90 bg-zinc-950/90 shadow-xl focus-within:border-indigo-500/60 focus-within:ring-1 focus-within:ring-indigo-500/40 transition-all backdrop-blur-md">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full resize-none bg-transparent px-4 pt-3.5 pb-12 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none disabled:opacity-50 min-h-[52px] max-h-[180px]"
        />

        <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {onOpenSourceModal && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onOpenSourceModal}
                className="h-8 gap-1.5 rounded-lg px-2.5 text-xs text-zinc-400 hover:text-indigo-300 hover:bg-zinc-800/60 border border-transparent hover:border-zinc-700/50 transition-all"
                title="Attach Source Document (PDF, YouTube, Web URL)"
              >
                <Paperclip className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Attach Source</span>
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] text-zinc-400 hidden md:inline select-none">
              Shift + Enter for new line
            </span>
            <Button
              type="button"
              size="icon"
              disabled={disabled || !input.trim()}
              onClick={handleSend}
              className="h-8 w-8 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 transition-transform active:scale-95 shadow-md shadow-indigo-950/50"
            >
              <ArrowUp className="h-4 w-4" />
              <span className="sr-only">Send message</span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

