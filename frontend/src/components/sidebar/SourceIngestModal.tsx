"use client";

import React, { useState } from "react";
import { FileText, Youtube, Globe, Upload, CheckCircle2, AlertCircle, GitBranch } from "lucide-react";
import { api } from "../../lib/api/client";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/tabs";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

interface SourceIngestModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  threadId: string;
  onSourceAdded?: () => void;
}

export function SourceIngestModal({
  open,
  onOpenChange,
  threadId,
  onSourceAdded,
}: SourceIngestModalProps) {
  const [activeTab, setActiveTab] = useState<string>("pdf");

  // PDF state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfSuccess, setPdfSuccess] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // YouTube state
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [ytLoading, setYtLoading] = useState(false);
  const [ytSuccess, setYtSuccess] = useState<string | null>(null);
  const [ytError, setYtError] = useState<string | null>(null);

  // Web URL state
  const [webUrl, setWebUrl] = useState("");
  const [webLoading, setWebLoading] = useState(false);
  const [webSuccess, setWebSuccess] = useState<string | null>(null);
  const [webError, setWebError] = useState<string | null>(null);

  // GitHub Repo state
  const [repoUrl, setRepoUrl] = useState("");
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoSuccess, setRepoSuccess] = useState<string | null>(null);
  const [repoError, setRepoError] = useState<string | null>(null);

  const resetStates = () => {
    setSelectedFile(null);
    setPdfSuccess(null);
    setPdfError(null);
    setYoutubeUrl("");
    setYtSuccess(null);
    setYtError(null);
    setWebUrl("");
    setWebSuccess(null);
    setWebError(null);
    setRepoUrl("");
    setRepoSuccess(null);
    setRepoError(null);
  };

  const handleUploadPdf = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setPdfError("Please select a PDF file to upload.");
      return;
    }

    try {
      setPdfLoading(true);
      setPdfError(null);
      setPdfSuccess(null);
      const res = await api.uploadPdf(selectedFile, threadId);
      setPdfSuccess(`PDF ingested successfully! (${res.status})`);
      setSelectedFile(null);
      onSourceAdded?.();
    } catch (err: any) {
      setPdfError(err?.message || "Failed to upload and ingest PDF.");
    } finally {
      setPdfLoading(false);
    }
  };

  const handleSetYoutube = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!youtubeUrl.trim()) {
      setYtError("Please enter a valid YouTube URL.");
      return;
    }

    try {
      setYtLoading(true);
      setYtError(null);
      setYtSuccess(null);
      const res = await api.setYoutube(youtubeUrl.trim(), threadId);
      setYtSuccess(`YouTube transcript indexed successfully! (${res.status})`);
      setYoutubeUrl("");
      onSourceAdded?.();
    } catch (err: any) {
      setYtError(err?.message || "Failed to ingest YouTube video transcript.");
    } finally {
      setYtLoading(false);
    }
  };

  const handleUploadWebUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!webUrl.trim()) {
      setWebError("Please enter a website URL.");
      return;
    }

    try {
      setWebLoading(true);
      setWebError(null);
      setWebSuccess(null);
      const res = await api.uploadUrl(webUrl.trim(), threadId);
      setWebSuccess(`Web page "${res.title || 'Source'}" indexed successfully!`);
      setWebUrl("");
      onSourceAdded?.();
    } catch (err: any) {
      setWebError(err?.message || "Failed to scrape and index web URL.");
    } finally {
      setWebLoading(false);
    }
  };

  const handleUploadRepo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) {
      setRepoError("Please enter a valid GitHub repository URL.");
      return;
    }
    if (!repoUrl.trim().startsWith("https://github.com/")) {
      setRepoError("URL must begin with https://github.com/owner/repo");
      return;
    }

    try {
      setRepoLoading(true);
      setRepoError(null);
      setRepoSuccess(null);
      const res = await api.uploadRepo(repoUrl.trim(), threadId);
      setRepoSuccess(res.message || `GitHub repository indexed (${res.file_count || 0} files)!`);
      setRepoUrl("");
      onSourceAdded?.();
    } catch (err: any) {
      setRepoError(err?.message || "Failed to index GitHub repository.");
    } finally {
      setRepoLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(val) => {
        if (!val) resetStates();
        onOpenChange(val);
      }}
    >
      <DialogHeader>
        <DialogTitle>Ground Assistant with Knowledge</DialogTitle>
        <DialogDescription>
          Attach external sources to this conversation thread for verified, grounded answers.
        </DialogDescription>
      </DialogHeader>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 mb-4">
          <TabsTrigger value="pdf" className="flex items-center gap-1 text-xs">
            <FileText className="h-3.5 w-3.5 text-rose-400" />
            <span>PDF</span>
          </TabsTrigger>
          <TabsTrigger value="youtube" className="flex items-center gap-1 text-xs">
            <Youtube className="h-3.5 w-3.5 text-red-500" />
            <span>YouTube</span>
          </TabsTrigger>
          <TabsTrigger value="web" className="flex items-center gap-1 text-xs">
            <Globe className="h-3.5 w-3.5 text-blue-400" />
            <span>Web</span>
          </TabsTrigger>
          <TabsTrigger value="github" className="flex items-center gap-1 text-xs">
            <GitBranch className="h-3.5 w-3.5 text-emerald-400" />
            <span>GitHub</span>
          </TabsTrigger>
        </TabsList>

        {/* PDF TAB */}
        <TabsContent value="pdf">
          <form onSubmit={handleUploadPdf} className="space-y-4">
            {pdfSuccess && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{pdfSuccess}</span>
              </div>
            )}
            {pdfError && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{pdfError}</span>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300">
                Choose PDF Document
              </label>
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/60 p-6 text-center hover:border-zinc-700 transition-colors">
                <Upload className="h-8 w-8 text-zinc-500 mb-2" />
                <p className="text-xs text-zinc-300 mb-1">
                  Drag and drop your PDF here, or click to browse
                </p>
                <p className="text-[11px] text-zinc-400">
                  Document will be chunked, embedded, and added to the thread vectorstore.
                </p>
                <input
                  type="file"
                  accept="application/pdf"
                  className="mt-4 block w-full text-xs text-zinc-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-medium file:bg-zinc-800 file:text-zinc-200 hover:file:bg-zinc-700 cursor-pointer"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) setSelectedFile(file);
                  }}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                type="submit"
                disabled={!selectedFile || pdfLoading}
                isLoading={pdfLoading}
                className="w-full sm:w-auto"
              >
                Upload & Ingest PDF
              </Button>
            </DialogFooter>
          </form>
        </TabsContent>

        {/* YOUTUBE TAB */}
        <TabsContent value="youtube">
          <form onSubmit={handleSetYoutube} className="space-y-4">
            {ytSuccess && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{ytSuccess}</span>
              </div>
            )}
            {ytError && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{ytError}</span>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300" htmlFor="youtube-url">
                YouTube Video URL
              </label>
              <Input
                id="youtube-url"
                type="url"
                placeholder="https://www.youtube.com/watch?v=..."
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
              />
              <p className="text-[11px] text-zinc-400">
                The video transcript will be extracted and embedded for semantic retrieval.
              </p>
            </div>

            <DialogFooter>
              <Button
                type="submit"
                disabled={!youtubeUrl.trim() || ytLoading}
                isLoading={ytLoading}
                className="w-full sm:w-auto"
              >
                Index YouTube Video
              </Button>
            </DialogFooter>
          </form>
        </TabsContent>

        {/* WEB URL TAB */}
        <TabsContent value="web">
          <form onSubmit={handleUploadWebUrl} className="space-y-4">
            {webSuccess && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{webSuccess}</span>
              </div>
            )}
            {webError && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{webError}</span>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300" htmlFor="web-url">
                Article or Web Page URL
              </label>
              <Input
                id="web-url"
                type="url"
                placeholder="https://example.com/article"
                value={webUrl}
                onChange={(e) => setWebUrl(e.target.value)}
              />
              <p className="text-[11px] text-zinc-400">
                Clean web content will be extracted, chunked, and grounded into this thread.
              </p>
            </div>

            <DialogFooter>
              <Button
                type="submit"
                disabled={!webUrl.trim() || webLoading}
                isLoading={webLoading}
                className="w-full sm:w-auto"
              >
                Index Web Page
              </Button>
            </DialogFooter>
          </form>
        </TabsContent>

        {/* GITHUB REPO TAB */}
        <TabsContent value="github">
          <form onSubmit={handleUploadRepo} className="space-y-4">
            {repoSuccess && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{repoSuccess}</span>
              </div>
            )}
            {repoError && (
              <div className="flex items-center gap-2 p-3 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{repoError}</span>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300" htmlFor="repo-url">
                GitHub Repository URL
              </label>
              <Input
                id="repo-url"
                type="url"
                placeholder="https://github.com/owner/repository"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
              />
              <p className="text-[11px] text-zinc-400">
                RepoGuide will shallow-clone, filter source files, chunk with line-number metadata, and index vectors for hybrid code retrieval.
              </p>
            </div>

            <DialogFooter>
              <Button
                type="submit"
                disabled={!repoUrl.trim() || repoLoading}
                isLoading={repoLoading}
                className="w-full sm:w-auto"
              >
                Index Repository
              </Button>
            </DialogFooter>
          </form>
        </TabsContent>
      </Tabs>
    </Dialog>
  );
}
