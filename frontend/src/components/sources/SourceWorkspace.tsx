"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  Youtube,
  Globe,
  Upload,
  CheckCircle2,
  AlertCircle,
  Eye,
  X,
  ExternalLink,
  Download,
  Loader2,
  CheckSquare,
  Square,
  Sparkles,
  RefreshCw,
  Layers,
  ChevronDown,
  ChevronUp,
  Sun,
  Moon,
  GitBranch,
} from "lucide-react";
import { api } from "../../lib/api/client";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Badge } from "../ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/tabs";
import { cn } from "../../lib/utils";
import type { AttachedDocument } from "../../types/chat";

interface SourceWorkspaceProps {
  threadId: string | null;
  documents: AttachedDocument[];
  selectedDocIds: string[];
  onToggleDocSelection: (docId: string) => void;
  onSelectAllDocs: (selectAll: boolean) => void;
  onSourceAdded: () => void;
  activePreviewDoc: AttachedDocument | null;
  previewPage?: number | string;
  onSelectPreviewDoc: (doc: AttachedDocument | null, page?: number | string) => void;
  onCloseWorkspace?: () => void;
  theme?: "light" | "dark";
  onToggleTheme?: () => void;
}

export function SourceWorkspace({
  threadId,
  documents,
  selectedDocIds,
  onToggleDocSelection,
  onSelectAllDocs,
  onSourceAdded,
  activePreviewDoc,
  previewPage,
  onSelectPreviewDoc,
  onCloseWorkspace,
  theme = "light",
  onToggleTheme,
}: SourceWorkspaceProps) {
  // Ingestion form tabs: "pdf" | "youtube" | "web"
  const [ingestTab, setIngestTab] = useState<string>("pdf");
  const [showIngestForm, setShowIngestForm] = useState<boolean>(true);

  // Ingestion status states
  const [pdfFiles, setPdfFiles] = useState<FileList | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfStatus, setPdfStatus] = useState<{ success?: string; error?: string } | null>(null);

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [ytLoading, setYtLoading] = useState(false);
  const [ytStatus, setYtStatus] = useState<{ success?: string; error?: string } | null>(null);

  const [webUrl, setWebUrl] = useState("");
  const [webLoading, setWebLoading] = useState(false);
  const [webStatus, setWebStatus] = useState<{ success?: string; error?: string } | null>(null);

  const [repoUrl, setRepoUrl] = useState("");
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoStatus, setRepoStatus] = useState<{ success?: string; error?: string } | null>(null);

  // Active preview PDF blob URL state
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Load preview PDF when activePreviewDoc changes to a PDF
  useEffect(() => {
    let activeUrl: string | null = null;

    async function loadPdfPreview() {
      if (!threadId || !activePreviewDoc || activePreviewDoc.type !== "pdf") {
        setPreviewBlobUrl(null);
        return;
      }

      try {
        setPreviewLoading(true);
        setPreviewError(null);
        const blob = await api.getPdfBlob(threadId, activePreviewDoc.doc_id);
        activeUrl = URL.createObjectURL(blob);
        setPreviewBlobUrl(activeUrl);
      } catch (err: any) {
        setPreviewError(err?.message || "Failed to load PDF preview.");
      } finally {
        setPreviewLoading(false);
      }
    }

    loadPdfPreview();

    return () => {
      if (activeUrl) {
        URL.revokeObjectURL(activeUrl);
      }
    };
  }, [threadId, activePreviewDoc]);

  // Handle PDF Upload (supports single or multiple files)
  const handleUploadPdf = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!threadId) {
      setPdfStatus({ error: "Please select or create a conversation thread first." });
      return;
    }
    if (!pdfFiles || pdfFiles.length === 0) {
      setPdfStatus({ error: "Please select at least one PDF file." });
      return;
    }

    try {
      setPdfLoading(true);
      setPdfStatus(null);

      let successCount = 0;
      for (let i = 0; i < pdfFiles.length; i++) {
        const file = pdfFiles[i];
        await api.uploadPdf(file, threadId);
        successCount++;
      }

      setPdfStatus({
        success: `Successfully uploaded and indexed ${successCount} PDF file(s)!`,
      });
      setPdfFiles(null);
      // Reset input value in DOM if present
      const fileInput = document.getElementById("pdf-workspace-input") as HTMLInputElement;
      if (fileInput) fileInput.value = "";

      onSourceAdded();
    } catch (err: any) {
      setPdfStatus({ error: err?.message || "Failed to upload and index PDF." });
    } finally {
      setPdfLoading(false);
    }
  };

  // Handle YouTube Indexing
  const handleSetYoutube = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!threadId) {
      setYtStatus({ error: "Please select or create a conversation thread first." });
      return;
    }
    if (!youtubeUrl.trim()) {
      setYtStatus({ error: "Please enter a valid YouTube URL." });
      return;
    }

    try {
      setYtLoading(true);
      setYtStatus(null);
      const res = await api.setYoutube(youtubeUrl.trim(), threadId);
      setYtStatus({
        success: `YouTube transcript indexed successfully (${res.status})!`,
      });
      setYoutubeUrl("");
      onSourceAdded();
    } catch (err: any) {
      setYtStatus({ error: err?.message || "Failed to ingest YouTube video transcript." });
    } finally {
      setYtLoading(false);
    }
  };

  // Handle Web Page Indexing
  const handleUploadWebUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!threadId) {
      setWebStatus({ error: "Please select or create a conversation thread first." });
      return;
    }
    if (!webUrl.trim()) {
      setWebStatus({ error: "Please enter a website or article URL." });
      return;
    }

    try {
      setWebLoading(true);
      setWebStatus(null);
      const res = await api.uploadUrl(webUrl.trim(), threadId);
      setWebStatus({
        success: `Web page "${res.title || "Article"}" indexed successfully!`,
      });
      setWebUrl("");
      onSourceAdded();
    } catch (err: any) {
      setWebStatus({ error: err?.message || "Failed to scrape and index web URL." });
    } finally {
      setWebLoading(false);
    }
  };

  // Handle GitHub Repo Indexing via RepoGuide
  const handleUploadRepo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!threadId) {
      setRepoStatus({ error: "Please select or create a conversation thread first." });
      return;
    }
    if (!repoUrl.trim()) {
      setRepoStatus({ error: "Please enter a valid GitHub repository URL." });
      return;
    }
    if (!repoUrl.trim().startsWith("https://github.com/")) {
      setRepoStatus({ error: "URL must begin with https://github.com/owner/repo" });
      return;
    }

    try {
      setRepoLoading(true);
      setRepoStatus(null);
      const res = await api.uploadRepo(repoUrl.trim(), threadId);
      setRepoStatus({
        success: res.message || `GitHub repository indexed (${res.file_count || 0} files)!`,
      });
      setRepoUrl("");
      onSourceAdded();
    } catch (err: any) {
      setRepoStatus({ error: err?.message || "Failed to index GitHub repository." });
    } finally {
      setRepoLoading(false);
    }
  };

  // Helper for YouTube embed URL
  const getYoutubeEmbedUrl = (source?: string) => {
    if (!source) return null;
    let videoId = source;
    if (source.includes("v=")) {
      videoId = source.split("v=")[1]?.split("&")[0];
    } else if (source.includes("youtu.be/")) {
      videoId = source.split("youtu.be/")[1]?.split("?")[0];
    }
    return `https://www.youtube.com/embed/${videoId}`;
  };

  const allSelected = documents.length > 0 && selectedDocIds.length === documents.length;
  const isLight = theme === "light";

  return (
    <div
      className={cn(
        "flex h-screen w-full flex-col border-l overflow-hidden select-text transition-colors duration-200",
        isLight ? "bg-[#fdfaff] border-pink-100 text-slate-800" : "bg-[#0b0c14] border-zinc-800/80 text-white"
      )}
    >
      {/* Workspace Header */}
      <div
        className={cn(
          "flex h-16 shrink-0 items-center justify-between border-b px-4 backdrop-blur-md z-10 transition-colors",
          isLight ? "border-pink-100/90 bg-white/80" : "border-zinc-800/80 bg-zinc-950/60"
        )}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-pink-500/15 border border-pink-500/30 text-pink-500 shrink-0">
            <Layers className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className={cn("text-sm font-semibold truncate", isLight ? "text-slate-800" : "text-zinc-100")}>
                Source Workspace
              </h2>
              <Badge variant="default" className="text-[10px] px-1.5 py-0 font-medium shrink-0">
                {selectedDocIds.length} / {documents.length} Active for RAG
              </Badge>
            </div>
            <p className={cn("text-[11px] truncate", isLight ? "text-slate-500" : "text-zinc-400")}>
              Attach & select sources to ground conversation answers
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Light/Dark Theme Toggle Button */}
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

          {onCloseWorkspace && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onCloseWorkspace}
              className={cn(
                "h-8 w-8 lg:hidden",
                isLight ? "text-slate-500 hover:text-slate-800" : "text-zinc-400 hover:text-white"
              )}
              title="Close Workspace"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Ingest Control Section */}
        <div
          className={cn(
            "rounded-xl border p-3.5 transition-colors",
            isLight
              ? "border-pink-100 bg-white shadow-xs"
              : "border-zinc-800/90 bg-zinc-950/70 shadow-md"
          )}
        >
          <div
            className={cn(
              "flex items-center justify-between pb-2 mb-2 border-b",
              isLight ? "border-pink-100/80" : "border-zinc-800/60"
            )}
          >
            <span
              className={cn(
                "text-xs font-semibold flex items-center gap-1.5",
                isLight ? "text-slate-800" : "text-zinc-200"
              )}
            >
              <Sparkles className="h-3.5 w-3.5 text-pink-500" />
              <span>Add Grounding Sources</span>
            </span>
            <button
              type="button"
              onClick={() => setShowIngestForm((prev) => !prev)}
              className="text-zinc-400 hover:text-zinc-200 text-xs flex items-center gap-1 transition-colors"
            >
              {showIngestForm ? (
                <>
                  <span className="text-[11px]">Collapse</span>
                  <ChevronUp className="h-3.5 w-3.5" />
                </>
              ) : (
                <>
                  <span className="text-[11px]">Attach Source</span>
                  <ChevronDown className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>

          {showIngestForm && (
            <Tabs value={ingestTab} onValueChange={setIngestTab}>
              <TabsList className="grid w-full grid-cols-4 mb-3 bg-zinc-900/60">
                <TabsTrigger value="pdf" className="flex items-center gap-1 text-[11px] py-1">
                  <FileText className="h-3 w-3 text-rose-400" />
                  <span>PDF</span>
                </TabsTrigger>
                <TabsTrigger value="youtube" className="flex items-center gap-1 text-[11px] py-1">
                  <Youtube className="h-3 w-3 text-red-500" />
                  <span>YouTube</span>
                </TabsTrigger>
                <TabsTrigger value="web" className="flex items-center gap-1 text-[11px] py-1">
                  <Globe className="h-3 w-3 text-blue-400" />
                  <span>Web</span>
                </TabsTrigger>
                <TabsTrigger value="github" className="flex items-center gap-1 text-[11px] py-1">
                  <GitBranch className="h-3 w-3 text-emerald-400" />
                  <span>GitHub</span>
                </TabsTrigger>
              </TabsList>

              {/* PDF Ingest Form */}
              <TabsContent value="pdf" className="space-y-3 mt-0">
                {pdfStatus?.success && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span>{pdfStatus.success}</span>
                  </div>
                )}
                {pdfStatus?.error && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{pdfStatus.error}</span>
                  </div>
                )}

                <form onSubmit={handleUploadPdf} className="space-y-2.5">
                  <div className="flex items-center justify-center rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 p-4 text-center hover:border-zinc-700 transition-colors">
                    <label className="flex flex-col items-center cursor-pointer w-full">
                      <Upload className="h-5 w-5 text-zinc-500 mb-1" />
                      <span className="text-xs text-zinc-300 font-medium">
                        {pdfFiles && pdfFiles.length > 0
                          ? `${pdfFiles.length} file(s) selected`
                          : "Upload PDF (supports multi-selection)"}
                      </span>
                      <span className="text-[10px] text-zinc-500 mt-0.5">
                        Extracted text & vector embeddings stored securely
                      </span>
                      <input
                        id="pdf-workspace-input"
                        type="file"
                        accept="application/pdf"
                        multiple
                        className="hidden"
                        onChange={(e) => setPdfFiles(e.target.files)}
                      />
                    </label>
                  </div>

                  <Button
                    type="submit"
                    disabled={!pdfFiles || pdfFiles.length === 0 || pdfLoading}
                    isLoading={pdfLoading}
                    size="sm"
                    className="w-full bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white text-xs h-8 shadow-xs"
                  >
                    Upload & Ingest to Thread
                  </Button>
                </form>
              </TabsContent>

              {/* YouTube Ingest Form */}
              <TabsContent value="youtube" className="space-y-3 mt-0">
                {ytStatus?.success && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span>{ytStatus.success}</span>
                  </div>
                )}
                {ytStatus?.error && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{ytStatus.error}</span>
                  </div>
                )}

                <form onSubmit={handleSetYoutube} className="space-y-2.5">
                  <div className="flex gap-2">
                    <Input
                      type="url"
                      placeholder="https://www.youtube.com/watch?v=..."
                      value={youtubeUrl}
                      onChange={(e) => setYoutubeUrl(e.target.value)}
                      className="h-8 text-xs bg-zinc-950/80 border-zinc-800"
                    />
                    <Button
                      type="submit"
                      disabled={!youtubeUrl.trim() || ytLoading}
                      isLoading={ytLoading}
                      size="sm"
                      className="h-8 shrink-0 bg-red-600 hover:bg-red-500 text-white text-xs px-3"
                    >
                      Index Video
                    </Button>
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    Captions with timestamps will be extracted and made available for question answering.
                  </p>
                </form>
              </TabsContent>

              {/* Web URL Ingest Form */}
              <TabsContent value="web" className="space-y-3 mt-0">
                {webStatus?.success && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span>{webStatus.success}</span>
                  </div>
                )}
                {webStatus?.error && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{webStatus.error}</span>
                  </div>
                )}

                <form onSubmit={handleUploadWebUrl} className="space-y-2.5">
                  <div className="flex gap-2">
                    <Input
                      type="url"
                      placeholder="https://example.com/article"
                      value={webUrl}
                      onChange={(e) => setWebUrl(e.target.value)}
                      className="h-8 text-xs bg-zinc-950/80 border-zinc-800"
                    />
                    <Button
                      type="submit"
                      disabled={!webUrl.trim() || webLoading}
                      isLoading={webLoading}
                      size="sm"
                      className="h-8 shrink-0 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3"
                    >
                      Index URL
                    </Button>
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    Clean content will be extracted, chunked, and embedded into this thread.
                  </p>
                </form>
              </TabsContent>

              {/* GitHub Repo Ingest Form */}
              <TabsContent value="github" className="space-y-3 mt-0">
                {repoStatus?.success && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    <span>{repoStatus.success}</span>
                  </div>
                )}
                {repoStatus?.error && (
                  <div className="flex items-center gap-2 p-2 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{repoStatus.error}</span>
                  </div>
                )}

                <form onSubmit={handleUploadRepo} className="space-y-2.5">
                  <div className="flex items-center gap-2">
                    <Input
                      type="url"
                      placeholder="https://github.com/owner/repository"
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                      className="h-8 text-xs bg-zinc-950/80 border-zinc-800"
                    />
                    <Button
                      type="submit"
                      disabled={!repoUrl.trim() || repoLoading}
                      isLoading={repoLoading}
                      size="sm"
                      className="h-8 shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3"
                    >
                      Index Repo
                    </Button>
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    RepoGuide will shallow-clone, chunk with line ranges, and embed vectors for code Q&A.
                  </p>
                </form>
              </TabsContent>
            </Tabs>
          )}
        </div>

        {/* Multi-Source Management Section */}
        <div
          className={cn(
            "rounded-xl border p-3.5 space-y-3 transition-colors",
            isLight
              ? "border-pink-100 bg-white shadow-xs"
              : "border-zinc-800/90 bg-zinc-950/70 shadow-md"
          )}
        >
          <div
            className={cn(
              "flex items-center justify-between pb-2 border-b",
              isLight ? "border-pink-100/80 text-slate-800" : "border-zinc-800/60 text-zinc-200"
            )}
          >
            <span className="text-xs font-semibold">
              Attached Sources ({documents.length})
            </span>

            {documents.length > 0 && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onSelectAllDocs(!allSelected)}
                  className="text-[11px] text-pink-500 hover:text-pink-400 font-medium transition-colors"
                >
                  {allSelected ? "Deselect All" : "Select All for RAG"}
                </button>
              </div>
            )}
          </div>

          {documents.length === 0 ? (
            <div className={cn("py-6 text-center text-xs italic", isLight ? "text-slate-400" : "text-zinc-500")}>
              No sources attached to this thread yet. Use the form above to upload PDFs, YouTube videos, or articles.
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => {
                const isSelected = selectedDocIds.includes(doc.doc_id);
                const isPreviewing = activePreviewDoc?.doc_id === doc.doc_id;

                return (
                  <div
                    key={doc.doc_id}
                    className={cn(
                      "flex items-center justify-between gap-3 p-2.5 rounded-lg border transition-all text-xs",
                      isPreviewing
                        ? "border-pink-500/60 bg-pink-950/20"
                        : isSelected
                        ? isLight
                          ? "border-pink-200 bg-pink-50/50 text-slate-900"
                          : "border-zinc-800 bg-zinc-900/60 hover:border-zinc-700"
                        : isLight
                        ? "border-pink-100/70 bg-slate-50/60 text-slate-600 hover:bg-white"
                        : "border-zinc-850 bg-zinc-950/40 opacity-70 hover:opacity-100"
                    )}
                  >
                    {/* Checkbox for RAG selection */}
                    <button
                      type="button"
                      onClick={() => onToggleDocSelection(doc.doc_id)}
                      className="text-zinc-400 hover:text-pink-400 shrink-0 transition-colors"
                      title={isSelected ? "Exclude from RAG query" : "Include in RAG query"}
                    >
                      {isSelected ? (
                        <CheckSquare className="h-4 w-4 text-pink-500" />
                      ) : (
                        <Square className="h-4 w-4 text-zinc-600" />
                      )}
                    </button>

                    {/* Source Type Icon & Details */}
                    <div
                      className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer"
                      onClick={() => onSelectPreviewDoc(doc)}
                    >
                      {doc.type === "pdf" && <FileText className="h-4 w-4 text-rose-400 shrink-0" />}
                      {doc.type === "youtube" && <Youtube className="h-4 w-4 text-red-500 shrink-0" />}
                      {doc.type === "web" && <Globe className="h-4 w-4 text-blue-400 shrink-0" />}
                      {(doc.type === "github" || doc.type === "repo") && <GitBranch className="h-4 w-4 text-emerald-400 shrink-0" />}

                      <div className="min-w-0 flex-1">
                        <p className="text-zinc-200 font-medium truncate">
                          {doc.filename || doc.title || doc.source || "Document"}
                        </p>
                        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                          <span className="uppercase">{doc.type}</span>
                          <span>•</span>
                          <span className="text-emerald-400 font-medium">Ready</span>
                        </div>
                      </div>
                    </div>

                    {/* Preview Button */}
                    <Button
                      variant={isPreviewing ? "default" : "ghost"}
                      size="sm"
                      onClick={() => onSelectPreviewDoc(isPreviewing ? null : doc)}
                      className={cn(
                        "h-7 px-2 text-[11px] gap-1 shrink-0",
                        isPreviewing
                          ? "bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 text-white"
                          : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                      )}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span>{isPreviewing ? "Viewing" : "Preview"}</span>
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Embedded Active Preview Workspace */}
        {activePreviewDoc && (
          <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/90 shadow-xl overflow-hidden flex flex-col">
            {/* Preview Toolbar */}
            <div className="flex items-center justify-between px-3.5 py-2.5 bg-zinc-900/80 border-b border-zinc-800 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                {activePreviewDoc.type === "pdf" && <FileText className="h-4 w-4 text-rose-400 shrink-0" />}
                {activePreviewDoc.type === "youtube" && <Youtube className="h-4 w-4 text-red-500 shrink-0" />}
                {activePreviewDoc.type === "web" && <Globe className="h-4 w-4 text-blue-400 shrink-0" />}
                {(activePreviewDoc.type === "github" || activePreviewDoc.type === "repo") && <GitBranch className="h-4 w-4 text-emerald-400 shrink-0" />}
                <span className="font-semibold text-zinc-100 truncate">
                  {activePreviewDoc.filename || activePreviewDoc.title || activePreviewDoc.source}
                  {previewPage ? ` (Page ${previewPage})` : ""}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {previewBlobUrl && activePreviewDoc.type === "pdf" && (
                  <a
                    href={previewBlobUrl}
                    download={`${activePreviewDoc.filename || "document"}.pdf`}
                    className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded hover:bg-zinc-800 transition-colors"
                  >
                    <Download className="h-3 w-3" />
                    <span>Download</span>
                  </a>
                )}
                <button
                  type="button"
                  onClick={() => onSelectPreviewDoc(null)}
                  className="text-zinc-400 hover:text-zinc-200 p-1 rounded hover:bg-zinc-800 transition-colors"
                  title="Close Preview"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Preview Viewer Area */}
            <div className="min-h-[380px] max-h-[500px] flex flex-col items-center justify-center bg-black/60 overflow-hidden">
              {previewLoading && (
                <div className="flex flex-col items-center gap-2 text-zinc-400 p-8">
                  <Loader2 className="h-7 w-7 animate-spin text-pink-500" />
                  <span className="text-xs">Loading document preview...</span>
                </div>
              )}

              {previewError && (
                <div className="p-6 text-center text-xs text-rose-400">
                  <p>{previewError}</p>
                </div>
              )}

              {!previewLoading && !previewError && activePreviewDoc.type === "pdf" && previewBlobUrl && (
                <iframe
                  src={previewPage ? `${previewBlobUrl}#page=${previewPage}` : previewBlobUrl}
                  className="w-full h-[450px] border-0"
                  title="PDF Preview"
                />
              )}

              {!previewLoading && activePreviewDoc.type === "youtube" && (
                <iframe
                  src={getYoutubeEmbedUrl(activePreviewDoc.source) || ""}
                  className="w-full h-[320px] border-0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  title="YouTube Preview"
                />
              )}

              {!previewLoading && activePreviewDoc.type === "web" && (
                <div className="p-8 text-center space-y-3">
                  <Globe className="h-10 w-10 text-blue-400 mx-auto opacity-75" />
                  <p className="text-xs text-zinc-300 font-medium">External Web Article</p>
                  <p className="text-[11px] text-zinc-500 max-w-sm mx-auto truncate">
                    {activePreviewDoc.source}
                  </p>
                  <a
                    href={activePreviewDoc.source}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
                  >
                    Open Page in Browser
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              {!previewLoading && (activePreviewDoc.type === "github" || activePreviewDoc.type === "repo") && (
                <div className="p-8 text-center space-y-3">
                  <GitBranch className="h-10 w-10 text-emerald-400 mx-auto opacity-75" />
                  <p className="text-xs text-zinc-300 font-semibold">{activePreviewDoc.filename || "GitHub Repository"}</p>
                  <p className="text-[11px] text-zinc-400 max-w-sm mx-auto truncate font-mono">
                    {activePreviewDoc.source}
                  </p>
                  <p className="text-[11px] text-zinc-500 max-w-sm mx-auto">
                    Indexed with RepoGuide hybrid retrieval (pgvector + full-text search + filename matching). Ask questions in chat to query this codebase.
                  </p>
                  <a
                    href={activePreviewDoc.source}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
                  >
                    Open on GitHub
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

