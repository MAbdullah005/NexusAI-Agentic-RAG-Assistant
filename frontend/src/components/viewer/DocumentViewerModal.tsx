"use client";

import React, { useState, useEffect } from "react";
import { FileText, Youtube, Globe, Download, ExternalLink, X, Loader2 } from "lucide-react";
import { api } from "../../lib/api/client";
import { Dialog, DialogHeader, DialogTitle, DialogDescription } from "../ui/dialog";
import { Button } from "../ui/button";

interface DocumentViewerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  threadId: string;
  docId?: string;
  title?: string;
  docType?: "pdf" | "youtube" | "web" | string;
  sourceUrl?: string;
  page?: number | string;
}

export function DocumentViewerModal({
  open,
  onOpenChange,
  threadId,
  docId,
  title = "Document Viewer",
  docType = "pdf",
  sourceUrl,
  page,
}: DocumentViewerModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activeUrl: string | null = null;

    async function loadPdf() {
      if (!open || docType !== "pdf" || !docId || !threadId) return;

      try {
        setLoading(true);
        setError(null);
        const blob = await api.getPdfBlob(threadId, docId);
        activeUrl = URL.createObjectURL(blob);
        setBlobUrl(activeUrl);
      } catch (err: any) {
        setError(err?.message || "Failed to load PDF document.");
      } finally {
        setLoading(false);
      }
    }

    if (docType === "pdf") {
      loadPdf();
    }

    return () => {
      if (activeUrl) {
        URL.revokeObjectURL(activeUrl);
      }
    };
  }, [open, threadId, docId, docType]);

  // Handle YouTube embed URL
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          {docType === "pdf" && <FileText className="h-4 w-4 text-rose-400" />}
          {docType === "youtube" && <Youtube className="h-4 w-4 text-red-500" />}
          {docType === "web" && <Globe className="h-4 w-4 text-blue-400" />}
          <h3 className="font-semibold text-zinc-100 text-sm truncate max-w-md">
            {title} {page ? `(Page ${page})` : ""}
          </h3>
        </div>

        {blobUrl && (
          <a
            href={blobUrl}
            download={`${title || 'document'}.pdf`}
            className="mr-6 inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Download</span>
          </a>
        )}
      </div>

      <div className="mt-4 min-h-[450px] max-h-[75vh] flex flex-col items-center justify-center rounded-lg bg-zinc-950 overflow-hidden border border-zinc-900">
        {loading && (
          <div className="flex flex-col items-center gap-2 text-zinc-400">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
            <span className="text-xs">Loading document securely...</span>
          </div>
        )}

        {error && (
          <div className="p-4 text-center text-xs text-rose-400">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && docType === "pdf" && blobUrl && (
          <iframe
            src={page ? `${blobUrl}#page=${page}` : blobUrl}
            className="w-full h-[65vh] border-0 rounded-lg"
            title="PDF Document Viewer"
          />
        )}

        {!loading && docType === "youtube" && sourceUrl && (
          <iframe
            src={getYoutubeEmbedUrl(sourceUrl) || ""}
            className="w-full h-[55vh] border-0 rounded-lg"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            title="YouTube Video Player"
          />
        )}

        {!loading && docType === "web" && sourceUrl && (
          <div className="p-8 text-center space-y-4">
            <Globe className="h-12 w-12 text-blue-400 mx-auto opacity-70" />
            <p className="text-sm text-zinc-300 font-medium">External Web Resource</p>
            <p className="text-xs text-zinc-500 max-w-sm truncate">{sourceUrl}</p>
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              Open Web Page in New Tab
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        )}
      </div>
    </Dialog>
  );
}

