"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
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
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Trash2,
  Check,
  X,
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
  onRenameThread?: (threadId: string, newTitle: string) => void;
  onPinThread?: (threadId: string, pinned: boolean) => void;
  onDeleteThread?: (threadId: string) => void;
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
  onRenameThread,
  onPinThread,
  onDeleteThread,
}: SidebarProps) {
  const { user, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const isLight = theme === "light";

  // Menu / rename / delete state
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const deleteConfirmRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Close menu and delete confirmation on outside click or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null);
      }
      if (deleteConfirmRef.current && !deleteConfirmRef.current.contains(e.target as Node)) {
        setDeleteConfirmId(null);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenMenuId(null);
        setRenamingId(null);
        setDeleteConfirmId(null);
      }
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);

  // Auto-focus rename input when it appears
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const commitRename = (threadId: string) => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== threads.find((t) => t.thread_id === threadId)?.title) {
      onRenameThread?.(threadId, trimmed);
    }
    setRenamingId(null);
  };

  // Filter threads by search query
  const filteredThreads = useMemo(() => {
    if (!searchQuery.trim()) return threads;
    const q = searchQuery.toLowerCase();
    return threads.filter((t) => t.title?.toLowerCase().includes(q));
  }, [threads, searchQuery]);

  // Separate pinned and unpinned
  const pinnedThreads = useMemo(
    () => filteredThreads.filter((t) => t.is_pinned),
    [filteredThreads]
  );
  const unpinnedThreads = useMemo(
    () => filteredThreads.filter((t) => !t.is_pinned),
    [filteredThreads]
  );

  // Group unpinned threads chronologically
  const groupedThreads = useMemo(() => {
    const groups: Record<string, Thread[]> = {};
    for (const thread of unpinnedThreads) {
      const label = formatDateLabel(thread.created_at);
      if (!groups[label]) {
        groups[label] = [];
      }
      groups[label].push(thread);
    }
    return groups;
  }, [unpinnedThreads]);

  const groupOrder = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older", "Earlier"];

  // Render a single thread row (shared between pinned + grouped sections)
  const renderThreadItem = (t: Thread) => {
    const isActive = t.thread_id === activeThreadId;
    const isMenuOpen = openMenuId === t.thread_id;
    const isRenaming = renamingId === t.thread_id;
    const isConfirmingDelete = deleteConfirmId === t.thread_id;

    return (
      <div key={t.thread_id} className="relative group/item">
        {/* Main thread button */}
        <button
          onClick={() => {
            if (isRenaming || isConfirmingDelete) return;
            onSelectThread(t.thread_id);
            onCloseMobile?.();
          }}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-xs transition-all",
            isActive
              ? isLight
                ? "bg-pink-50 text-pink-700 font-semibold border border-pink-200/80 shadow-xs"
                : "bg-pink-500/15 text-pink-300 font-medium border border-pink-500/30"
              : isLight
              ? "text-slate-600 hover:bg-pink-50/50 hover:text-slate-900"
              : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
          )}
        >
          <MessageSquare
            className={cn(
              "h-3.5 w-3.5 shrink-0",
              isActive
                ? "text-pink-500"
                : isLight
                ? "text-slate-400 group-hover/item:text-pink-500"
                : "text-zinc-400 group-hover/item:text-zinc-300"
            )}
          />

          {/* Title or rename input */}
          {isRenaming ? (
            <input
              ref={renameInputRef}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename(t.thread_id);
                if (e.key === "Escape") setRenamingId(null);
                e.stopPropagation();
              }}
              onBlur={() => commitRename(t.thread_id)}
              onClick={(e) => e.stopPropagation()}
              className={cn(
                "flex-1 min-w-0 bg-transparent border-b outline-none text-xs",
                isLight ? "border-pink-400 text-slate-900" : "border-pink-400 text-white"
              )}
            />
          ) : (
            <span className="truncate flex-1 pr-6">{t.title || "Untitled Chat"}</span>
          )}

          {/* Pinned indicator */}
          {t.is_pinned && !isRenaming && (
            <Pin
              className={cn(
                "h-3 w-3 shrink-0 group-hover/item:hidden",
                isLight ? "text-pink-500" : "text-pink-400"
              )}
            />
          )}

          {/* Active dot (hide when menu button is shown) */}
          {isActive && !isRenaming && (
            <div className="h-1.5 w-1.5 rounded-full bg-pink-500 shrink-0 group-hover/item:hidden" />
          )}
        </button>

        {/* Three-dot menu button — shown on hover */}
        {!isRenaming && !isConfirmingDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setOpenMenuId(isMenuOpen ? null : t.thread_id);
            }}
            title="More options"
            className={cn(
              "absolute right-1.5 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-lg transition-all",
              "opacity-0 group-hover/item:opacity-100",
              isMenuOpen ? "opacity-100" : "",
              isLight
                ? "text-slate-500 hover:bg-pink-100 hover:text-slate-800"
                : "text-zinc-500 hover:bg-zinc-700 hover:text-zinc-200"
            )}
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </button>
        )}

        {/* Dropdown menu */}
        {isMenuOpen && (
          <div
            ref={menuRef}
            className={cn(
              "absolute right-1 top-8 z-50 w-36 rounded-xl border shadow-xl py-1 overflow-hidden",
              isLight
                ? "bg-white border-pink-100 shadow-pink-100/50"
                : "bg-zinc-900 border-zinc-700/80 shadow-black/40"
            )}
          >
            {/* Rename */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setRenamingId(t.thread_id);
                setRenameValue(t.title || "");
                setOpenMenuId(null);
              }}
              className={cn(
                "flex items-center gap-2 w-full px-3 py-1.5 text-xs text-left transition-colors",
                isLight
                  ? "text-slate-700 hover:bg-pink-50 hover:text-slate-900"
                  : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
              )}
            >
              <Pencil className="h-3.5 w-3.5" />
              Rename
            </button>

            {/* Pin / Unpin */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPinThread?.(t.thread_id, !t.is_pinned);
                setOpenMenuId(null);
              }}
              className={cn(
                "flex items-center gap-2 w-full px-3 py-1.5 text-xs text-left transition-colors",
                isLight
                  ? "text-slate-700 hover:bg-pink-50 hover:text-slate-900"
                  : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
              )}
            >
              {t.is_pinned ? (
                <PinOff className="h-3.5 w-3.5" />
              ) : (
                <Pin className="h-3.5 w-3.5" />
              )}
              {t.is_pinned ? "Unpin" : "Pin"}
            </button>

            {/* Divider */}
            <div
              className={cn(
                "my-1 border-t",
                isLight ? "border-pink-100" : "border-zinc-700/60"
              )}
            />

            {/* Delete */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setDeleteConfirmId(t.thread_id);
                setOpenMenuId(null);
              }}
              className={cn(
                "flex items-center gap-2 w-full px-3 py-1.5 text-xs text-left transition-colors",
                "text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10"
              )}
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        )}

        {/* Inline delete confirmation */}
        {isConfirmingDelete && (
          <div
            ref={deleteConfirmRef}
            className={cn(
              "mx-1 mt-0.5 mb-1 flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[11px]",
              isLight
                ? "bg-rose-50 border border-rose-200 text-rose-700"
                : "bg-rose-500/10 border border-rose-500/30 text-rose-300"
            )}
          >
            <Trash2 className="h-3 w-3 shrink-0" />
            <span className="flex-1">Delete this chat?</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteThread?.(t.thread_id);
                setDeleteConfirmId(null);
              }}
              title="Confirm delete"
              className="rounded px-1.5 py-0.5 bg-rose-500 text-white hover:bg-rose-600 transition-colors"
            >
              Yes
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setDeleteConfirmId(null);
              }}
              title="Cancel"
              className={cn(
                "rounded px-1.5 py-0.5 transition-colors",
                isLight
                  ? "bg-slate-200 text-slate-700 hover:bg-slate-300"
                  : "bg-zinc-700 text-zinc-200 hover:bg-zinc-600"
              )}
            >
              No
            </button>
          </div>
        )}
      </div>
    );
  };

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
            <>
              {/* Pinned section */}
              {pinnedThreads.length > 0 && (
                <div className="space-y-1">
                  <h4
                    className={cn(
                      "flex items-center gap-1.5 px-2.5 text-[11px] font-semibold tracking-wider uppercase",
                      isLight ? "text-pink-500" : "text-pink-400"
                    )}
                  >
                    <Pin className="h-3 w-3" />
                    Pinned
                  </h4>
                  <div className="space-y-0.5">
                    {pinnedThreads.map((t) => renderThreadItem(t))}
                  </div>
                </div>
              )}

              {/* Date-grouped unpinned threads */}
              {groupOrder.map((group) => {
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
                      {items.map((t) => renderThreadItem(t))}
                    </div>
                  </div>
                );
              })}
            </>
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
