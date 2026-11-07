"use client";

import React, { useState, useRef, useEffect } from "react";
import { ArrowUp, Paperclip, Sparkles, Sliders } from "lucide-react";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";
import type { DeepResearchConfig } from "../../types/chat";

interface ChatComposerProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  onOpenSourceModal?: () => void;
  placeholder?: string;
  theme?: "light" | "dark";
  isDeepResearch?: boolean;
  onToggleDeepResearch?: () => void;
  onOpenResearchConfig?: () => void;
  researchConfig?: DeepResearchConfig;
}

export function ChatComposer({
  onSendMessage,
  disabled = false,
  onOpenSourceModal,
  placeholder = "Ask NexusAI",
  theme = "light",
  isDeepResearch = false,
  onToggleDeepResearch,
  onOpenResearchConfig,
  researchConfig,
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

  const isLight = theme === "light";

  return (
    <div className="w-full max-w-4xl mx-auto p-4">
      <div
        className={cn(
          "relative rounded-2xl border transition-all backdrop-blur-md",
          isLight
            ? "border-pink-200/90 bg-white/95 shadow-[0_10px_35px_-8px_rgba(244,114,182,0.18)] focus-within:border-pink-400 focus-within:ring-2 focus-within:ring-pink-100"
            : "border-pink-900/40 bg-zinc-950/90 shadow-xl focus-within:border-pink-500/60 focus-within:ring-1 focus-within:ring-pink-500/40"
        )}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isDeepResearch
              ? "Ask a question for Deep Research (investigating Web, arXiv, and Docs)..."
              : placeholder
          }
          disabled={disabled}
          className={cn(
            "w-full resize-none bg-transparent px-4 pt-3.5 pb-12 text-sm focus:outline-none disabled:opacity-50 min-h-[52px] max-h-[180px]",
            isLight
              ? "text-slate-900 placeholder:text-slate-400"
              : "text-zinc-100 placeholder:text-zinc-500"
          )}
        />

        <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between">
          <div className="flex items-center gap-1.5 flex-wrap">
            {onOpenSourceModal && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onOpenSourceModal}
                className={cn(
                  "h-8 gap-1.5 rounded-lg px-2.5 text-xs border border-transparent transition-all",
                  isLight
                    ? "text-slate-500 hover:text-pink-600 hover:bg-pink-50/80 hover:border-pink-200/60"
                    : "text-zinc-400 hover:text-pink-300 hover:bg-zinc-800/60 hover:border-zinc-700/50"
                )}
                title="Attach Source Document (PDF, YouTube, Web URL)"
              >
                <Paperclip className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Attach Source</span>
              </Button>
            )}

            {onToggleDeepResearch && (
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onToggleDeepResearch}
                  className={cn(
                    "h-8 gap-1.5 rounded-lg px-2.5 text-xs border transition-all",
                    isDeepResearch
                      ? "border-rose-500 bg-rose-500/15 text-rose-600 dark:text-rose-400 font-semibold shadow-xs ring-1 ring-rose-500/30"
                      : isLight
                      ? "border-slate-200/80 text-slate-600 hover:text-rose-600 hover:bg-rose-50/60"
                      : "border-zinc-800 text-zinc-400 hover:text-rose-300 hover:bg-zinc-800/60"
                  )}
                  title="Toggle Deep Research Mode (Web + arXiv + Docs)"
                >
                  <Sparkles
                    className={cn(
                      "h-3.5 w-3.5 transition-colors",
                      isDeepResearch ? "text-rose-500 fill-rose-500/30" : "text-slate-400 dark:text-zinc-500"
                    )}
                  />
                  <span>Deep Research</span>
                  {isDeepResearch && (
                    <span className="ml-0.5 text-[9px] font-extrabold uppercase tracking-wider text-rose-600 dark:text-rose-400 bg-rose-100 dark:bg-rose-950/80 px-1 py-0.2 rounded">
                      ON
                    </span>
                  )}
                </Button>

                {isDeepResearch && onOpenResearchConfig && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={onOpenResearchConfig}
                    className={cn(
                      "h-8 w-8 rounded-lg border text-xs transition-all",
                      isLight
                        ? "border-slate-200/80 text-slate-500 hover:text-rose-600 hover:bg-rose-50/60"
                        : "border-zinc-800 text-zinc-400 hover:text-rose-300 hover:bg-zinc-800/60"
                    )}
                    title="Configure Deep Research settings (length, citation style, search count)"
                  >
                    <Sliders className="h-3.5 w-3.5 text-rose-500 dark:text-rose-400" />
                    <span className="sr-only">Configure Deep Research</span>
                  </Button>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-[11px] hidden md:inline select-none",
                isLight ? "text-slate-400" : "text-zinc-500"
              )}
            >
              Shift + Enter for new line
            </span>
            <Button
              type="button"
              size="icon"
              disabled={disabled || !input.trim()}
              onClick={handleSend}
              className="h-8 w-8 rounded-xl bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white disabled:opacity-40 transition-transform active:scale-95 shadow-md shadow-pink-500/25"
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
