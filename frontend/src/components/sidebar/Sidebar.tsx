"use client";

import React, { useState, useMemo } from "react";
import {
  Bot,
  Plus,
  Search,
  MessageSquare,
  FileText,
  Youtube,
  Globe,
  LogOut,
  Sparkles,
  Paperclip,
  CheckCircle2,
  ChevronRight,
  ShieldCheck,
  FolderOpen,
} from "lucide-react";
import { cn, formatDateLabel } from "../../lib/utils";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { useAuth } from "../../hooks/useAuth";
import type { AttachedDocument, Thread } from "../../types/chat";

interface SidebarProps {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  creatingThread?: boolean;
  documents?: AttachedDocument[];
  onOpenSourceModal?: () => void;
  onViewDocument?: (doc: AttachedDocument) => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export function Sidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewChat,
  creatingThread = false,
  documents = [],
  onOpenSourceModal,
  onViewDocument,
  isOpenMobile = false,
  onCloseMobile,
}: SidebarProps) {
  const { user, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [showSourcesList, setShowSourcesList] = useState(true);

  // Filter threads by search query
  const filteredThreads = useMemo(() => {
    if (!searchQuery.trim()) return threads;
    const q = searchQuery.toLowerCase();
    return threads.filter((t) => t.title?.toLowerCase().includes(q));
  }, [threads, searchQuery]);

  // Group threads chronologically
  const groupedThreads = useMemo(() => {
    const groups: Record<string, Thread[]> = {};
    for (const thread of filteredThreads) {
      const label = formatDateLabel(thread.created_at);
      if (!groups[label]) {
        groups[label] = [];
      }
      groups[label].push(thread);
    }
    return groups;
  }, [filteredThreads]);

  const groupOrder = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older", "Earlier"];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-zinc-800/80 bg-[#0c0d14] transition-transform duration-200 lg:static lg:translate-x-0",
          isOpenMobile ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between border-b border-zinc-800/80 px-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-400">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 font-bold text-sm text-white tracking-tight">
                <span>NexusAI</span>
                <span className="rounded bg-indigo-500/20 px-1.5 py-0.2 text-[10px] font-medium text-indigo-300">
                  RAG
                </span>
              </div>
              <p className="text-[10px] text-zinc-400">Agentic Workspace</p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="p-3 space-y-2.5 border-b border-zinc-800/60">
          <Button
            onClick={onNewChat}
            disabled={creatingThread}
            isLoading={creatingThread}
            className="w-full justify-start gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-sm shadow-indigo-950/50"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat</span>
          </Button>

          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-500" />
            <Input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 pl-8 text-xs bg-zinc-950/50 border-zinc-800/90 focus-visible:ring-indigo-500/50"
            />
          </div>
        </div>

        {/* Thread History List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-4">
          {filteredThreads.length === 0 ? (
            <div className="py-8 text-center text-xs text-zinc-500">
              {searchQuery ? "No matching conversations." : "No conversations yet."}
            </div>
          ) : (
            groupOrder.map((group) => {
              const items = groupedThreads[group];
              if (!items || items.length === 0) return null;

              return (
                <div key={group} className="space-y-1">
                  <h4 className="px-2.5 text-[11px] font-semibold tracking-wider text-zinc-400 uppercase">
                    {group}
                  </h4>
                  <div className="space-y-0.5">
                    {items.map((t) => {
                      const isActive = t.thread_id === activeThreadId;
                      return (
                        <button
                          key={t.thread_id}
                          onClick={() => {
                            onSelectThread(t.thread_id);
                            onCloseMobile?.();
                          }}
                          className={cn(
                            "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition-colors group",
                            isActive
                              ? "bg-zinc-800 text-white font-medium border border-zinc-700/60"
                              : "text-zinc-400 hover:bg-zinc-850 hover:text-zinc-200"
                          )}
                        >
                          <MessageSquare
                            className={cn(
                              "h-3.5 w-3.5 shrink-0",
                              isActive ? "text-indigo-400" : "text-zinc-400 group-hover:text-zinc-300"
                            )}
                          />
                          <span className="truncate flex-1">{t.title || "Untitled Chat"}</span>
                          {isActive && (
                            <div className="h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Attached Sources Section for Active Thread */}
        {activeThreadId && (
          <div className="border-t border-zinc-800/80 bg-zinc-950/40 p-3 space-y-2">
            <div className="flex items-center justify-between text-xs text-zinc-400">
              <span className="flex items-center gap-1.5 font-medium">
                <FolderOpen className="h-3.5 w-3.5 text-indigo-400" />
                <span>Thread Sources ({documents.length})</span>
              </span>
              {onOpenSourceModal && (
                <button
                  onClick={onOpenSourceModal}
                  className="rounded px-1.5 py-0.5 text-[11px] text-indigo-400 hover:text-indigo-300 hover:bg-zinc-800/60 transition-colors"
                >
                  + Add
                </button>
              )}
            </div>

            {documents.length > 0 ? (
              <div className="max-h-28 overflow-y-auto space-y-1">
                {documents.map((doc) => (
                  <button
                    key={doc.doc_id}
                    onClick={() => onViewDocument?.(doc)}
                    className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-[11px] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors group"
                  >
                    {doc.type === "pdf" && <FileText className="h-3 w-3 text-rose-400 shrink-0" />}
                    {doc.type === "youtube" && <Youtube className="h-3 w-3 text-red-500 shrink-0" />}
                    {doc.type === "web" && <Globe className="h-3 w-3 text-blue-400 shrink-0" />}
                    <span className="truncate flex-1">
                      {doc.filename || doc.source || "Document"}
                    </span>
                    <ChevronRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-zinc-400 italic">No sources attached to this thread yet.</p>
            )}
          </div>
        )}

        {/* User Profile & Logout */}
        <div className="border-t border-zinc-800/80 bg-zinc-950/80 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0 pr-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-xs font-semibold text-zinc-200 border border-zinc-700/60">
                {user?.email?.charAt(0).toUpperCase() || "U"}
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-zinc-200">{user?.email}</p>
                <div className="flex items-center gap-1 text-[10px] text-zinc-400">
                  <ShieldCheck className="h-3 w-3 text-emerald-400" />
                  <span>Verified Member</span>
                </div>
              </div>
            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title="Sign Out"
              className="h-7 w-7 text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10"
            >
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </aside>
    </>
  );
}

