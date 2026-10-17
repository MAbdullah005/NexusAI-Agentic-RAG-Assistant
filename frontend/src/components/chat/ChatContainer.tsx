"use client";

import React, { useRef, useEffect } from "react";
import { Menu, Bot, Sparkles, BookOpen, FileText, Youtube, Globe, Layers } from "lucide-react";
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
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages or interrupt
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending, hitlInterrupt]);

  return (
    <div className="flex h-screen flex-1 flex-col bg-[#090a0f] overflow-hidden">
      {/* Top Navbar */}
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800/80 px-4 bg-zinc-950/60 backdrop-blur-md z-10">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSidebarMobile}
            className="lg:hidden text-zinc-400 hover:text-white"
          >
            <Menu className="h-5 w-5" />
          </Button>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-zinc-100 truncate">
                {activeThread?.title || "Select or start a chat"}
              </h2>
              <span className="rounded-full bg-indigo-500/15 border border-indigo-500/30 px-2 py-0.5 text-[10px] font-medium text-indigo-400 shrink-0">
                LangGraph Hybrid RAG
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 truncate">
              {documents.length > 0
                ? `${documents.length} source document(s) attached`
                : "No external sources attached"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onSelectMobileTab && (
            <div className="flex lg:hidden rounded-lg bg-zinc-900 border border-zinc-800 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => onSelectMobileTab("chat")}
                className="px-2.5 py-1 rounded-md font-medium text-white bg-zinc-800 shadow-sm"
              >
                Chat
              </button>
              <button
                type="button"
                onClick={() => onSelectMobileTab("sources")}
                className="px-2.5 py-1 rounded-md text-zinc-400 hover:text-zinc-200"
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
                "hidden lg:inline-flex text-xs gap-1.5 border-zinc-800 transition-colors",
                isWorkspaceOpen
                  ? "bg-indigo-600/20 border-indigo-500/40 text-indigo-300 hover:bg-indigo-600/30"
                  : "bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300"
              )}
            >
              <Layers className="h-3.5 w-3.5 text-indigo-400" />
              <span>{isWorkspaceOpen ? "Sources Panel" : "Open Sources"}</span>
              <span className="ml-1 rounded-full bg-zinc-800 px-1.5 py-0.2 text-[10px] text-zinc-300 border border-zinc-700/60">
                {documents.length}
              </span>
            </Button>
          )}

          {onOpenSourceModal && !isWorkspaceOpen && (
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenSourceModal}
              className="text-xs gap-1.5 border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hidden sm:inline-flex"
            >
              <BookOpen className="h-3.5 w-3.5 text-indigo-400" />
              <span>Attach Sources</span>
            </Button>
          )}
        </div>
      </header>

      {/* Messages Scroll Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-2 py-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex min-h-[70vh] flex-col items-center justify-center p-6 text-center max-w-xl mx-auto space-y-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-400 shadow-xl shadow-indigo-950/50">
              <Bot className="h-8 w-8" />
            </div>

            <div className="space-y-2">
              <h3 className="text-xl font-bold text-zinc-100 tracking-tight">
                How can NexusAI assist you today?
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed max-w-md mx-auto">
                Grounded conversational intelligence with multi-document PDF retrieval, YouTube video transcripts, web search fallback (CRAG), and durable memory.
              </p>
            </div>

            {/* Quick Prompt Starters */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 w-full pt-2">
              <button
                onClick={() =>
                  onSendMessage("What are the primary findings and conclusions of the attached document?")
                }
                className="flex flex-col items-start gap-1 p-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 hover:bg-zinc-850 hover:border-zinc-700/80 transition-all text-left group"
              >
                <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-200">
                  <FileText className="h-3.5 w-3.5 text-rose-400" />
                  <span>Analyze PDF</span>
                </div>
                <p className="text-[11px] text-zinc-400 line-clamp-2">
                  Extract findings, tables, and page citations.
                </p>
              </button>

              <button
                onClick={() =>
                  onSendMessage("Can you summarize the main themes of the linked YouTube video?")
                }
                className="flex flex-col items-start gap-1 p-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 hover:bg-zinc-850 hover:border-zinc-700/80 transition-all text-left group"
              >
                <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-200">
                  <Youtube className="h-3.5 w-3.5 text-red-500" />
                  <span>Video Summary</span>
                </div>
                <p className="text-[11px] text-zinc-400 line-clamp-2">
                  Retrieve key takeaways from the video transcript.
                </p>
              </button>

              <button
                onClick={() =>
                  onSendMessage("Search and verify current state-of-the-art developments in AI agent graphs.")
                }
                className="flex flex-col items-start gap-1 p-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 hover:bg-zinc-850 hover:border-zinc-700/80 transition-all text-left group"
              >
                <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-200">
                  <Globe className="h-3.5 w-3.5 text-blue-400" />
                  <span>CRAG Search</span>
                </div>
                <p className="text-[11px] text-zinc-400 line-clamp-2">
                  Evaluate grounded sources with web search approval.
                </p>
              </button>
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
      <footer className="shrink-0 bg-gradient-to-t from-[#090a0f] via-[#090a0f]/95 to-transparent pb-2">
        <ChatComposer
          onSendMessage={onSendMessage}
          disabled={pending || !!hitlInterrupt}
          onOpenSourceModal={onOpenSourceModal}
        />
      </footer>
    </div>
  );
}

