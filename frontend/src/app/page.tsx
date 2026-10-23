"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { api } from "../lib/api/client";
import { Sidebar } from "../components/sidebar/Sidebar";
import { ChatContainer } from "../components/chat/ChatContainer";
import { SourceWorkspace } from "../components/sources/SourceWorkspace";
import { SourceIngestModal } from "../components/sidebar/SourceIngestModal";
import { DocumentViewerModal } from "../components/viewer/DocumentViewerModal";
import { cn } from "../lib/utils";
import type { AttachedDocument, ChatMessage, HITLInterruptData, Thread } from "../types/chat";

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
      let threadList: Thread[] = (rawThreads || [])
        .map((t: any) => ({
          thread_id: String(t.thread_id || t.id || ""),
          title: t.title || "New Chat",
          created_at: t.created_at ? String(t.created_at) : new Date().toISOString(),
        }))
        .filter((t) => Boolean(t.thread_id));

      if (threadList.length === 0) {
        // Automatically create an initial conversation thread so activeThreadId is never null
        const res = await api.createThread();
        const newThreadId = res.thread_id;
        const initialThread: Thread = {
          thread_id: newThreadId,
          title: "New Chat",
          created_at: new Date().toISOString(),
        };
        threadList = [initialThread];
      }

      setThreads(threadList);

      // Auto-select first thread if none active, or preserve existing active thread if valid
      setActiveThreadId((current) => {
        if (current && threadList.some((t) => t.thread_id === current)) {
          return current;
        }
        return threadList[0].thread_id;
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

  // Create new thread
  const handleNewChat = async () => {
    try {
      setCreatingThread(true);
      const res = await api.createThread();
      const newThreadId = res.thread_id;
      const newThread: Thread = {
        thread_id: newThreadId,
        title: "New Chat",
        created_at: new Date().toISOString(),
      };
      setThreads((prev) => [newThread, ...prev.filter((t) => t.thread_id !== newThreadId)]);
      setActiveThreadId(newThreadId);
      setMessages([]);
      setDocuments([]);
      setSelectedDocIds([]);
      setHitlInterrupt(null);
      setActivePreviewDoc(null);
      setActiveMobileTab("chat");
    } catch (err) {
      console.error("Failed to create new thread:", err);
    } finally {
      setCreatingThread(false);
    }
  };

  // Send message
  const handleSendMessage = async (text: string) => {
    let currentThreadId = activeThreadId;

    // If no thread exists yet, create one first
    if (!currentThreadId) {
      try {
        setCreatingThread(true);
        const res = await api.createThread();
        const newThreadId = res.thread_id;
        currentThreadId = newThreadId;
        const newThread: Thread = {
          thread_id: newThreadId,
          title: "New Chat",
          created_at: new Date().toISOString(),
        };
        setThreads((prev) => [newThread, ...prev.filter((t) => t.thread_id !== newThreadId)]);
        setActiveThreadId(newThreadId);
      } catch (err) {
        console.error("Failed to create thread before sending message:", err);
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

        // Generate dynamic title if this was the first user message in thread
        const currentThread = threads.find((t) => t.thread_id === currentThreadId);
        if (
          user?.user_id &&
          currentThread &&
          (currentThread.title === "New Chat" || currentThread.title.startsWith("Chat "))
        ) {
          api
            .generateTitle(currentThreadId, user.user_id, text)
            .then((res) => {
              if (res.title) {
                setThreads((prev) =>
                  prev.map((t) =>
                    t.thread_id === currentThreadId ? { ...t, title: res.title } : t
                  )
                );
              }
            })
            .catch((e) => console.warn("Background title generation error:", e));
        }
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
      {activeThreadId && (
        <SourceIngestModal
          open={sourceModalOpen}
          onOpenChange={setSourceModalOpen}
          threadId={activeThreadId}
          onSourceAdded={() => {
            loadThreadDetails(activeThreadId);
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
    </div>
  );
}
