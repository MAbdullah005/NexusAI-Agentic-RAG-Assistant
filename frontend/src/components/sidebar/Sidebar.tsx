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
  theme?: "light" | "dark";
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
  theme = "light",
}: SidebarProps) {
  const { user, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const isLight = theme === "light";

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
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r transition-all duration-200 lg:static lg:translate-x-0",
          isLight
            ? "bg-white border-pink-100 text-slate-800"
            : "bg-[#0c0d14] border-zinc-800/80 text-white",
          isOpenMobile ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand Header */}
        <div
          className={cn(
            "flex h-16 items-center justify-between border-b px-4 transition-colors",
            isLight ? "border-pink-100" : "border-zinc-800/80"
          )}
        >
          <div className="flex items-center gap-2.5">
            <img
              src="/nexus-logo.png"
              alt="NexusAI Logo"
              className="h-8 w-8 object-contain rounded-xl shadow-xs"
            />
            <div>
              <div className="flex items-center gap-1.5 font-bold text-sm tracking-tight">
                <span className={isLight ? "text-slate-900" : "text-white"}>NexusAI</span>
                <span className="rounded-full bg-pink-500/15 border border-pink-500/30 px-1.5 py-0.2 text-[10px] font-semibold text-pink-600 dark:text-pink-300">
                  Assistant
                </span>
              </div>
              <p className={cn("text-[10px]", isLight ? "text-slate-500" : "text-zinc-400")}>
                Conversational Workspace
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div
          className={cn(
            "p-3 space-y-2.5 border-b transition-colors",
            isLight ? "border-pink-100/80" : "border-zinc-800/60"
          )}
        >
          <Button
            onClick={onNewChat}
            disabled={creatingThread}
            isLoading={creatingThread}
            className="w-full justify-start gap-2 bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white font-medium shadow-sm shadow-pink-500/25"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat</span>
          </Button>

          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-400" />
            <Input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={cn(
                "h-8 pl-8 text-xs transition-colors",
                isLight
                  ? "bg-slate-50 border-pink-100 text-slate-800 placeholder:text-slate-400 focus-visible:ring-pink-300"
                  : "bg-zinc-950/50 border-zinc-800/90 text-white placeholder:text-zinc-500 focus-visible:ring-pink-500/50"
              )}
            />
          </div>
        </div>

        {/* Thread History List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-4">
          {filteredThreads.length === 0 ? (
            <div className={cn("py-8 text-center text-xs", isLight ? "text-slate-400" : "text-zinc-500")}>
              {searchQuery ? "No matching conversations." : "No conversations yet."}
            </div>
          ) : (
            groupOrder.map((group) => {
              const items = groupedThreads[group];
              if (!items || items.length === 0) return null;

              return (
                <div key={group} className="space-y-1">
                  <h4
                    className={cn(
                      "px-2.5 text-[11px] font-semibold tracking-wider uppercase",
                      isLight ? "text-slate-400" : "text-zinc-500"
                    )}
                  >
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
                            "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-xs transition-all group",
                            isActive
                              ? isLight
                                ? "bg-pink-50 text-pink-700 font-semibold border border-pink-200/80 shadow-xs"
                                : "bg-pink-500/15 text-pink-300 font-medium border border-pink-500/30"
                              : isLight
                              ? "text-slate-600 hover:bg-pink-50/50 hover:text-slate-900"
                              : "text-zinc-400 hover:bg-zinc-850 hover:text-zinc-200"
                          )}
                        >
                          <MessageSquare
                            className={cn(
                              "h-3.5 w-3.5 shrink-0",
                              isActive
                                ? "text-pink-500"
                                : isLight
                                ? "text-slate-400 group-hover:text-pink-500"
                                : "text-zinc-400 group-hover:text-zinc-300"
                            )}
                          />
                          <span className="truncate flex-1">{t.title || "Untitled Chat"}</span>
                          {isActive && (
                            <div className="h-1.5 w-1.5 rounded-full bg-pink-500 shrink-0" />
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
          <div
            className={cn(
              "border-t p-3 space-y-2 transition-colors",
              isLight ? "border-pink-100 bg-pink-50/30" : "border-zinc-800/80 bg-zinc-950/40"
            )}
          >
            <div className="flex items-center justify-between text-xs">
              <span className={cn("flex items-center gap-1.5 font-medium", isLight ? "text-slate-700" : "text-zinc-300")}>
                <FolderOpen className="h-3.5 w-3.5 text-pink-500" />
                <span>Thread Sources ({documents.length})</span>
              </span>
              {onOpenSourceModal && (
                <button
                  onClick={onOpenSourceModal}
                  className="rounded px-1.5 py-0.5 text-[11px] font-medium text-pink-600 hover:text-pink-700 transition-colors"
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
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-[11px] transition-colors group",
                      isLight
                        ? "text-slate-600 hover:text-slate-900 hover:bg-pink-100/50"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                    )}
                  >
                    {doc.type === "pdf" && <FileText className="h-3 w-3 text-rose-500 shrink-0" />}
                    {doc.type === "youtube" && <Youtube className="h-3 w-3 text-red-500 shrink-0" />}
                    {doc.type === "web" && <Globe className="h-3 w-3 text-blue-500 shrink-0" />}
                    <span className="truncate flex-1">
                      {doc.filename || doc.source || "Document"}
                    </span>
                    <ChevronRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            ) : (
              <p className={cn("text-[11px] italic", isLight ? "text-slate-400" : "text-zinc-500")}>
                No sources attached to this thread yet.
              </p>
            )}
          </div>
        )}

        {/* User Profile & Logout */}
        <div
          className={cn(
            "border-t p-3 transition-colors",
            isLight ? "border-pink-100 bg-white" : "border-zinc-800/80 bg-zinc-950/80"
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0 pr-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-pink-500 to-rose-400 text-xs font-semibold text-white shadow-xs">
                {user?.email?.charAt(0).toUpperCase() || "U"}
              </div>
              <div className="min-w-0">
                <p className={cn("truncate text-xs font-medium", isLight ? "text-slate-800" : "text-zinc-200")}>
                  {user?.email}
                </p>
                <div className="flex items-center gap-1 text-[10px] text-pink-600 dark:text-pink-400">
                  <ShieldCheck className="h-3 w-3" />
                  <span>Verified User</span>
                </div>
              </div>
            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title="Sign Out"
              className={cn(
                "h-7 w-7 transition-colors",
                isLight
                  ? "text-slate-500 hover:text-rose-600 hover:bg-rose-50"
                  : "text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10"
              )}
            >
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </aside>
    </>
  );
}
