"use client";

import React, { useRef, useEffect } from "react";
import { Menu, Bot, Sparkles, BookOpen, Layers, Sun, Moon } from "lucide-react";
import { Button } from "../ui/button";
import { ChatMessageItem } from "./ChatMessageItem";
import { HITLBanner } from "./HITLBanner";
import { ChatComposer } from "./ChatComposer";
import { cn } from "../../lib/utils";
import type { AttachedDocument, ChatMessage, HITLInterruptData, Thread } from "../../types/chat";

interface ChatContainerProps {
  activeThread: Thread | null;
  messages: ChatMessage[];
  pending: boolean;
  hitlInterrupt: HITLInterruptData | null;
  documents: AttachedDocument[];
  onSendMessage: (text: string) => void;
  onResumeHITL: (decision: "yes" | "no") => Promise<void>;
  onOpenSourceModal?: () => void;
  onViewPdf: (docId: string, page?: number | string) => void;
  onToggleSidebarMobile: () => void;
  onToggleWorkspace?: () => void;
  isWorkspaceOpen?: boolean;
  onSelectMobileTab?: (tab: "chat" | "sources") => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

export function ChatContainer({
  activeThread,
  messages,
  pending,
  hitlInterrupt,
  documents,
  onSendMessage,
  onResumeHITL,
  onOpenSourceModal,
  onViewPdf,
  onToggleSidebarMobile,
  onToggleWorkspace,
  isWorkspaceOpen = true,
  onSelectMobileTab,
  theme = "light",
  onToggleTheme,
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const isLight = theme === "light";

  // Auto-scroll on new messages or interrupt
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending, hitlInterrupt]);

  return (
    <div
      className={cn(
        "flex h-screen flex-1 flex-col transition-colors duration-200 overflow-hidden",
        isLight ? "bg-[#fdfaff]" : "bg-[#090a0f]"
      )}
    >
      {/* Top Navbar */}
      <header
        className={cn(
          "flex h-16 shrink-0 items-center justify-between border-b px-4 backdrop-blur-md z-10 transition-colors",
          isLight
            ? "border-pink-100/90 bg-white/80"
            : "border-zinc-800/80 bg-zinc-950/60"
        )}
      >
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSidebarMobile}
            className={cn(
              "lg:hidden",
              isLight ? "text-slate-600 hover:text-slate-900" : "text-zinc-400 hover:text-white"
            )}
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="min-w-0">
            <h2
              className={cn(
                "text-sm font-semibold truncate",
                isLight ? "text-slate-800" : "text-zinc-100"
              )}
            >
              {activeThread?.title || "Select or start a chat"}
            </h2>
            <p
              className={cn(
                "text-[11px] truncate",
                isLight ? "text-slate-500" : "text-zinc-400"
              )}
            >
              {documents.length > 0
                ? `${documents.length} source document(s) attached`
                : "No external sources attached"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* NexusAI Logo beside NexusAI Assistant — Conversational Workspace in top-right area */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-colors border-pink-100/90 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/60 shadow-xs">
            <img
              src="/nexus-logo.png"
              alt="NexusAI Logo"
              className="h-7 w-7 object-contain rounded-lg"
            />
            <div className="hidden sm:flex flex-col text-left">
              <span className={cn("text-xs font-bold leading-tight", isLight ? "text-slate-800" : "text-zinc-100")}>
                NexusAI Assistant
              </span>
              <span className={cn("text-[10px] leading-tight", isLight ? "text-slate-500" : "text-zinc-400")}>
                Conversational Workspace
              </span>
            </div>
          </div>

          {/* Theme Toggle Button */}
          {onToggleTheme && (
            <button
              type="button"
              onClick={onToggleTheme}
              aria-label="Toggle Theme"
              className={cn(
                "p-2 rounded-xl transition-all border",
                isLight
                  ? "bg-white border-pink-200/80 text-pink-600 hover:bg-pink-50 shadow-xs"
                  : "bg-zinc-800/80 border-zinc-700 text-amber-300 hover:bg-zinc-700"
              )}
              title={isLight ? "Switch to Dark Theme" : "Switch to Light Theme"}
            >
              {isLight ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </button>
          )}

          {onSelectMobileTab && (
            <div
              className={cn(
                "flex lg:hidden rounded-lg p-0.5 text-xs border",
                isLight ? "bg-pink-50 border-pink-100" : "bg-zinc-900 border-zinc-800"
              )}
            >
              <button
                type="button"
                onClick={() => onSelectMobileTab("chat")}
                className={cn(
                  "px-2.5 py-1 rounded-md font-medium shadow-xs transition-colors",
                  isLight ? "bg-white text-pink-600 font-semibold" : "bg-zinc-800 text-white"
                )}
              >
                Chat
              </button>
              <button
                type="button"
                onClick={() => onSelectMobileTab("sources")}
                className={cn(
                  "px-2.5 py-1 rounded-md transition-colors",
                  isLight ? "text-slate-600 hover:text-slate-900" : "text-zinc-400 hover:text-zinc-200"
                )}
              >
                Sources ({documents.length})
              </button>
            </div>
          )}

          {onToggleWorkspace && (
            <Button
              variant="outline"
              size="sm"
              onClick={onToggleWorkspace}
              className={cn(
                "hidden lg:inline-flex text-xs gap-1.5 transition-colors",
                isLight
                  ? isWorkspaceOpen
                    ? "bg-pink-500/10 border-pink-300 text-pink-600 hover:bg-pink-500/20"
                    : "bg-white border-pink-100 hover:bg-pink-50 text-slate-700"
                  : isWorkspaceOpen
                  ? "bg-pink-600/20 border-pink-500/40 text-pink-300 hover:bg-pink-600/30"
                  : "bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 border-zinc-800"
              )}
            >
              <Layers className="h-3.5 w-3.5 text-pink-500" />
              <span>{isWorkspaceOpen ? "Sources Panel" : "Open Sources"}</span>
              <span
                className={cn(
                  "ml-1 rounded-full px-1.5 py-0.2 text-[10px] border",
                  isLight
                    ? "bg-pink-50 text-pink-700 border-pink-200"
                    : "bg-zinc-800 text-zinc-300 border-zinc-700/60"
                )}
              >
                {documents.length}
              </span>
            </Button>
          )}

          {onOpenSourceModal && !isWorkspaceOpen && (
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenSourceModal}
              className={cn(
                "text-xs gap-1.5 hidden sm:inline-flex transition-colors",
                isLight
                  ? "border-pink-200 bg-white hover:bg-pink-50 text-pink-600"
                  : "border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300"
              )}
            >
              <BookOpen className="h-3.5 w-3.5 text-pink-500" />
              <span>Attach Sources</span>
            </Button>
          )}
        </div>
      </header>

      {/* Messages Scroll Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-2 py-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex min-h-[65vh] flex-col items-center justify-center p-6 text-center max-w-xl mx-auto space-y-3">
            {/* Main Welcome Content */}
            <div className="space-y-1.5">
              <h3
                className={cn(
                  "text-2xl sm:text-3xl font-extrabold tracking-tight",
                  isLight ? "text-slate-900" : "text-zinc-100"
                )}
              >
                How can NexusAI assist you today?
              </h3>

              {/* Subtle Example Prompt as simple text */}
              <p
                className={cn(
                  "text-sm font-normal tracking-normal select-none pt-1",
                  isLight ? "text-slate-500" : "text-zinc-400"
                )}
              >
                What’s on today’s agenda?
              </p>
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-4">
            {messages.map((msg, index) => (
              <ChatMessageItem
                key={msg.id || index}
                message={msg}
                threadId={activeThread?.thread_id}
                onViewPdf={onViewPdf}
                theme={theme}
              />
            ))}

            {pending && (
              <ChatMessageItem
                message={{
                  role: "assistant",
                  content: "",
                  pending: true,
                }}
                threadId={activeThread?.thread_id}
                onViewPdf={onViewPdf}
                theme={theme}
              />
            )}
          </div>
        )}

        {/* HITL Interrupt Banner */}
        {hitlInterrupt && (
          <div className="max-w-4xl mx-auto">
            <HITLBanner
              interrupt={hitlInterrupt}
              onResume={onResumeHITL}
            />
          </div>
        )}
      </div>

      {/* Composer Footer */}
      <footer
        className={cn(
          "shrink-0 pb-2 transition-colors",
          isLight
            ? "bg-gradient-to-t from-[#fdfaff] via-[#fdfaff]/95 to-transparent"
            : "bg-gradient-to-t from-[#090a0f] via-[#090a0f]/95 to-transparent"
        )}
      >
        <ChatComposer
          onSendMessage={onSendMessage}
          disabled={pending || !!hitlInterrupt}
          onOpenSourceModal={onOpenSourceModal}
          placeholder="Ask NexusAI"
          theme={theme}
        />
      </footer>
    </div>
  );
}
