"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { api } from "../lib/api/client";
import { Sidebar } from "../components/sidebar/Sidebar";
import { ChatContainer } from "../components/chat/ChatContainer";
import { SourceWorkspace } from "../components/sources/SourceWorkspace";
import { SourceIngestModal } from "../components/sidebar/SourceIngestModal";
import { DocumentViewerModal } from "../components/viewer/DocumentViewerModal";
import { DeepResearchModal } from "../components/chat/DeepResearchModal";
import { cn } from "../lib/utils";
import type {
  AttachedDocument,
  ChatMessage,
  HITLInterruptData,
  Thread,
  DeepResearchConfig,
  ResearchStageUpdate,
  ResearchSource,
} from "../types/chat";

export default function ChatPage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();

  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [documents, setDocuments] = useState<AttachedDocument[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [threadSummary, setThreadSummary] = useState<string | null>(null);

  const [loadingThreads, setLoadingThreads] = useState<boolean>(true);
  const [creatingThread, setCreatingThread] = useState<boolean>(false);
  const [pendingMessage, setPendingMessage] = useState<boolean>(false);
  const [hitlInterrupt, setHitlInterrupt] = useState<HITLInterruptData | null>(null);

  // Deep Research state
  const [isDeepResearch, setIsDeepResearch] = useState<boolean>(false);
  const [researchConfig, setResearchConfig] = useState<DeepResearchConfig>({
    search_count: 10,
    report_length: "long",
    citation_style: "APA",
    subqueries_count: 3,
    iterations: 1,
    instructions: "",
  });
  const [researchModalOpen, setResearchModalOpen] = useState<boolean>(false);
  const [activeResearchUpdate, setActiveResearchUpdate] = useState<ResearchStageUpdate | null>(null);
  const researchAbortRef = useRef<(() => void) | null>(null);

  // Theme state: defaults to light mode
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const savedTheme = localStorage.getItem("nexus_auth_theme") as "light" | "dark" | null;
    if (savedTheme === "dark") {
      setTheme("dark");
      document.documentElement.classList.add("dark");
    } else {
      setTheme("light");
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    localStorage.setItem("nexus_auth_theme", nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  // Split-screen workspace states
  const [workspaceOpen, setWorkspaceOpen] = useState<boolean>(true);
  const [activeMobileTab, setActiveMobileTab] = useState<"chat" | "sources">("chat");
  const [activePreviewDoc, setActivePreviewDoc] = useState<AttachedDocument | null>(null);
  const [previewPage, setPreviewPage] = useState<number | string | undefined>(undefined);

  // Modals state
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [viewerModalOpen, setViewerModalOpen] = useState(false);
  const [viewerDoc, setViewerDoc] = useState<{
    docId?: string;
    title?: string;
    docType?: "pdf" | "youtube" | "web" | string;
    sourceUrl?: string;
    page?: number | string;
  }>({});

  // Mobile sidebar state
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);

  // Authentication gate
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  // Load threads
  const loadThreads = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      setLoadingThreads(true);
      const rawThreads = await api.getThreads();
      const threadList: Thread[] = (rawThreads || [])
        .map((t: any) => ({
          thread_id: String(t.thread_id || t.id || ""),
          title: t.title || "New Chat",
          created_at: t.created_at ? String(t.created_at) : new Date().toISOString(),
          is_pinned: Boolean(t.is_pinned),
        }))
        .filter((t) => Boolean(t.thread_id));

      setThreads(threadList);

      // Preserve existing active thread if valid, or select first saved thread if none active
      setActiveThreadId((current) => {
        if (current && threadList.some((t) => t.thread_id === current)) {
          return current;
        }
        return threadList.length > 0 ? threadList[0].thread_id : null;
      });
    } catch (err) {
      console.error("Failed to load threads:", err);
    } finally {
      setLoadingThreads(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadThreads();
    }
  }, [isAuthenticated, loadThreads]);

  // Load active thread details (messages, documents, summary)
  const loadThreadDetails = useCallback(async (threadId: string) => {
    try {
      if (researchAbortRef.current) {
        researchAbortRef.current();
        researchAbortRef.current = null;
      }
      setActiveResearchUpdate(null);
      setHitlInterrupt(null);
      const details = await api.getThreadDetails(threadId);

      setMessages(
        details.messages.map((m) => ({
          role: m.role,
          content: m.content,
        }))
      );

      const docs = details.documents || [];
      setDocuments(docs);
      // Auto-select all attached documents for RAG by default
      setSelectedDocIds(docs.map((d) => d.doc_id));
      setThreadSummary(details.summary || null);
    } catch (err) {
      console.error(`Failed to load details for thread ${threadId}:`, err);
    }
  }, []);

  useEffect(() => {
    if (activeThreadId) {
      loadThreadDetails(activeThreadId);
    } else {
      setMessages([]);
      setDocuments([]);
      setSelectedDocIds([]);
      setThreadSummary(null);
      setActivePreviewDoc(null);
    }
  }, [activeThreadId, loadThreadDetails]);

  // Toggle selection of a document for RAG query
  const handleToggleDocSelection = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  // Select all or clear selection
  const handleSelectAllDocs = (selectAll: boolean) => {
    if (selectAll) {
      setSelectedDocIds(documents.map((d) => d.doc_id));
    } else {
      setSelectedDocIds([]);
    }
  };

  // Helper to ensure an active thread exists (used when uploading files or sending first message)
  const ensureActiveThread = useCallback(async (): Promise<string> => {
    if (activeThreadId) return activeThreadId;
    const res = await api.createThread();
    const newThreadId = res.thread_id;
    setActiveThreadId(newThreadId);
    return newThreadId;
  }, [activeThreadId]);

  // Start temporary new chat session
  const handleNewChat = useCallback(() => {
    // If already in an empty chat session (no messages), keep existing session active
    if (messages.length === 0 && (!activeThreadId || !threads.some((t) => t.thread_id === activeThreadId))) {
      return;
    }

    // Reset to an empty temporary chat session without saving anything to DB or sidebar
    if (researchAbortRef.current) {
      researchAbortRef.current();
      researchAbortRef.current = null;
    }
    setActiveResearchUpdate(null);
    setActiveThreadId(null);
    setMessages([]);
    setDocuments([]);
    setSelectedDocIds([]);
    setHitlInterrupt(null);
    setThreadSummary(null);
    setActivePreviewDoc(null);
    setActiveMobileTab("chat");
  }, [activeThreadId, messages.length, threads]);

  // Rename thread
  const handleRenameThread = useCallback(async (threadId: string, newTitle: string) => {
    try {
      await api.renameThread(threadId, newTitle);
      setThreads((prev) =>
        prev.map((t) => (t.thread_id === threadId ? { ...t, title: newTitle } : t))
      );
    } catch (err) {
      console.error("Failed to rename thread:", err);
    }
  }, []);

  // Pin / unpin thread
  const handlePinThread = useCallback(async (threadId: string, pinned: boolean) => {
    try {
      await api.pinThread(threadId, pinned);
      setThreads((prev) => {
        const updated = prev.map((t) =>
          t.thread_id === threadId ? { ...t, is_pinned: pinned } : t
        );
        return [...updated].sort((a, b) => {
          if (a.is_pinned && !b.is_pinned) return -1;
          if (!a.is_pinned && b.is_pinned) return 1;
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
      });
    } catch (err) {
      console.error("Failed to pin/unpin thread:", err);
    }
  }, []);

  // Delete thread
  const handleDeleteThread = useCallback(async (threadId: string) => {
    try {
      await api.deleteThread(threadId);
      setThreads((prev) => {
        const remaining = prev.filter((t) => t.thread_id !== threadId);
        setActiveThreadId((curr) => {
          if (curr !== threadId) return curr;
          return remaining.length > 0 ? remaining[0].thread_id : null;
        });
        return remaining;
      });
    } catch (err) {
      console.error("Failed to delete thread:", err);
    }
  }, []);

  // Send message
  const handleSendMessage = async (text: string) => {
    let currentThreadId = activeThreadId;
    const isFirstMessage = messages.length === 0;

    // If no thread exists yet, create one on first question submission
    if (!currentThreadId) {
      try {
        setCreatingThread(true);
        currentThreadId = await ensureActiveThread();
      } catch (err) {
        console.error("Failed to create thread before sending message:", err);
        setCreatingThread(false);
        return;
      } finally {
        setCreatingThread(false);
      }
    }

    const clientMsgId = `client_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const userMsg: ChatMessage = {
      id: clientMsgId,
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setPendingMessage(true);
    setHitlInterrupt(null);

    // If this is the first question, generate title and display the conversation in the sidebar
    if (isFirstMessage && currentThreadId) {
      const activeId = currentThreadId;
      api
        .generateTitle(activeId, user?.user_id || 1, text)
        .then((res) => {
          const finalTitle = res.title || text.slice(0, 30).trim() || "New Chat";
          setThreads((prev) => {
            const existingIndex = prev.findIndex((t) => t.thread_id === activeId);
            if (existingIndex >= 0) {
              return prev.map((t) =>
                t.thread_id === activeId ? { ...t, title: finalTitle } : t
              );
            }
            const newThreadEntry: Thread = {
              thread_id: activeId,
              title: finalTitle,
              created_at: new Date().toISOString(),
              is_pinned: false,
            };
            return [newThreadEntry, ...prev];
          });
        })
        .catch((e) => {
          console.warn("Background title generation error:", e);
          const fallbackTitle = text.slice(0, 30).trim() || "New Chat";
          setThreads((prev) => {
            if (prev.some((t) => t.thread_id === activeId)) return prev;
            return [
              {
                thread_id: activeId,
                title: fallbackTitle,
                created_at: new Date().toISOString(),
                is_pinned: false,
              },
              ...prev,
            ];
          });
        });
    }

    // ========================================================
    // DEEP RESEARCH STREAMING EXECUTION
    // ========================================================
    if (isDeepResearch) {
      setPendingMessage(true);
      setActiveResearchUpdate({
        stage: "planning",
        stage_message: "Initializing Deep Research investigation...",
      });

      const abortFn = api.streamResearch(
        {
          thread_id: currentThreadId,
          message: text,
          client_message_id: clientMsgId,
          selected_doc_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
          config: researchConfig,
        },
        (update: ResearchStageUpdate) => {
          setActiveResearchUpdate(update);
        },
        (report: string, sources?: ResearchSource[]) => {
          setActiveResearchUpdate(null);
          setPendingMessage(false);
          const assistantMsg: ChatMessage = {
            id: `resp_${clientMsgId}`,
            role: "assistant",
            content: report,
            createdAt: new Date().toISOString(),
            is_research: true,
            research_sources: sources,
          };
          setMessages((prev) => [...prev, assistantMsg]);
        },
        (err: any) => {
          console.error("Deep Research streaming error:", err);
          setActiveResearchUpdate(null);
          setPendingMessage(false);
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `⚠️ Deep Research Error: ${err?.message || "Failed to complete research."}`,
              createdAt: new Date().toISOString(),
              error: true,
            },
          ]);
        }
      );
      researchAbortRef.current = abortFn;
      return;
    }

    try {
      const response = await api.sendMessage({
        thread_id: currentThreadId,
        message: text,
        client_message_id: clientMsgId,
        selected_doc_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
      });

      if (response.status === "human-approval") {
        setPendingMessage(false);
        setHitlInterrupt(response.interrupt || {});
      } else if (response.status === "completed") {
        const assistantMsg: ChatMessage = {
          id: `resp_${clientMsgId}`,
          role: "assistant",
          content: response.response || "No response received.",
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setPendingMessage(false);
      }
    } catch (err: any) {
      console.error("Failed to send chat message:", err);
      setPendingMessage(false);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Error: ${err?.message || "Failed to generate answer. Please try again."}`,
          createdAt: new Date().toISOString(),
          error: true,
        },
      ]);
    }
  };

  // Resume HITL
  const handleResumeHITL = async (decision: "yes" | "no") => {
    if (!activeThreadId) return;

    try {
      setPendingMessage(true);
      const res = await api.resumeChat({
        thread_id: activeThreadId,
        decision,
      });

      if (res.status === "human-approval") {
        setHitlInterrupt(res.interrupt || {});
        setPendingMessage(false);
      } else if (res.status === "completed") {
        setHitlInterrupt(null);
        await loadThreadDetails(activeThreadId);
        setPendingMessage(false);
      }
    } catch (err: any) {
      console.error("Failed to resume chat:", err);
      setPendingMessage(false);
    }
  };

  // Handle viewing PDF or citation page jump
  const handleViewPdf = (docId: string, page?: number | string) => {
    const doc = documents.find((d) => d.doc_id === docId);
    if (doc) {
      setActivePreviewDoc(doc);
      setPreviewPage(page);
      setWorkspaceOpen(true);
      setActiveMobileTab("sources");
    } else {
      // Fallback modal if document not in current list
      setViewerDoc({
        docId,
        title: "Referenced Document",
        docType: "pdf",
        page,
      });
      setViewerModalOpen(true);
    }
  };

  const handleViewDocument = (doc: AttachedDocument) => {
    setActivePreviewDoc(doc);
    setPreviewPage(undefined);
    setWorkspaceOpen(true);
    setActiveMobileTab("sources");
  };

  const activeThread = threads.find((t) => t.thread_id === activeThreadId) || null;

  if (authLoading) {
    return (
      <div
        className={cn(
          "flex min-h-screen items-center justify-center transition-colors",
          theme === "light" ? "bg-[#fdfaff]" : "bg-[#090a0f]"
        )}
      >
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-pink-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex h-screen w-full overflow-hidden transition-colors duration-200",
        theme === "light" ? "bg-[#fdfaff] text-slate-900" : "bg-[#090a0f] text-white"
      )}
    >
      {/* Sidebar Navigation */}
      <Sidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={(id) => {
          setActiveThreadId(id);
          setActiveMobileTab("chat");
        }}
        onNewChat={handleNewChat}
        creatingThread={creatingThread}
        documents={documents}
        onOpenSourceModal={() => setSourceModalOpen(true)}
        onViewDocument={handleViewDocument}
        isOpenMobile={sidebarMobileOpen}
        onCloseMobile={() => setSidebarMobileOpen(false)}
        theme={theme}
        onRenameThread={handleRenameThread}
        onPinThread={handlePinThread}
        onDeleteThread={handleDeleteThread}
      />

      {/* Split-Screen Workspace: Chat Container + Source Workspace */}
      <div className="flex flex-1 h-screen overflow-hidden">
        {/* Left Panel: Chat Container */}
        <div
          className={cn(
            "h-full flex-col transition-all duration-200",
            workspaceOpen ? "flex w-full lg:w-1/2" : "flex w-full",
            activeMobileTab === "sources" ? "hidden lg:flex" : "flex"
          )}
        >
          <ChatContainer
            activeThread={activeThread}
            messages={messages}
            pending={pendingMessage}
            hitlInterrupt={hitlInterrupt}
            documents={documents}
            onSendMessage={handleSendMessage}
            onResumeHITL={handleResumeHITL}
            onOpenSourceModal={() => setSourceModalOpen(true)}
            onViewPdf={handleViewPdf}
            onToggleSidebarMobile={() => setSidebarMobileOpen((prev) => !prev)}
            onToggleWorkspace={() => setWorkspaceOpen((prev) => !prev)}
            isWorkspaceOpen={workspaceOpen}
            onSelectMobileTab={(tab) => setActiveMobileTab(tab)}
            theme={theme}
            onToggleTheme={toggleTheme}
            isDeepResearch={isDeepResearch}
            onToggleDeepResearch={() => setIsDeepResearch((prev) => !prev)}
            onOpenResearchConfig={() => setResearchModalOpen(true)}
            researchConfig={researchConfig}
            activeResearchUpdate={activeResearchUpdate}
          />
        </div>

        {/* Right Panel: Source Workspace */}
        {workspaceOpen && (
          <div
            className={cn(
              "h-full w-full lg:w-1/2 flex-col transition-all duration-200",
              activeMobileTab === "chat" ? "hidden lg:flex" : "flex"
            )}
          >
            <SourceWorkspace
              threadId={activeThreadId}
              documents={documents}
              selectedDocIds={selectedDocIds}
              onToggleDocSelection={handleToggleDocSelection}
              onSelectAllDocs={handleSelectAllDocs}
              onEnsureThreadId={ensureActiveThread}
              onSourceAdded={() => {
                if (activeThreadId) loadThreadDetails(activeThreadId);
              }}
              activePreviewDoc={activePreviewDoc}
              previewPage={previewPage}
              onSelectPreviewDoc={(doc, page) => {
                setActivePreviewDoc(doc);
                setPreviewPage(page);
              }}
              onCloseWorkspace={() => {
                setWorkspaceOpen(false);
                setActiveMobileTab("chat");
              }}
              theme={theme}
              onToggleTheme={toggleTheme}
            />
          </div>
        )}
      </div>

      {/* Fallback Ingest Source Modal */}
      {sourceModalOpen && (
        <SourceIngestModal
          open={sourceModalOpen}
          onOpenChange={setSourceModalOpen}
          threadId={activeThreadId}
          onEnsureThreadId={ensureActiveThread}
          onSourceAdded={() => {
            if (activeThreadId) loadThreadDetails(activeThreadId);
          }}
        />
      )}

      {/* Fallback Embedded Document Viewer Modal */}
      {activeThreadId && (
        <DocumentViewerModal
          open={viewerModalOpen}
          onOpenChange={setViewerModalOpen}
          threadId={activeThreadId}
          docId={viewerDoc.docId}
          title={viewerDoc.title}
          docType={viewerDoc.docType}
          sourceUrl={viewerDoc.sourceUrl}
          page={viewerDoc.page}
        />
      )}

      {/* Deep Research Configuration Modal */}
      <DeepResearchModal
        open={researchModalOpen}
        onOpenChange={setResearchModalOpen}
        config={researchConfig}
        onSaveConfig={(newConfig) => setResearchConfig(newConfig)}
        theme={theme}
      />
    </div>
  );
}
