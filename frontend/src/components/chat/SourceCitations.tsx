"use client";

import React, { useState } from "react";
import { FileText, Youtube, Globe, ExternalLink, ChevronDown, ChevronUp, BookOpen, GitBranch } from "lucide-react";

export interface CitationItem {
  type: "pdf" | "youtube" | "web" | "general" | "github";
  title: string;
  detail?: string;
  url?: string;
  page?: number | string;
  doc_id?: string;
}

interface SourceCitationsProps {
  content: string;
  threadId?: string;
  onViewPdf?: (docId: string, page?: number | string) => void;
}

// Helper to extract citation patterns from assistant response
export function extractCitations(text: string): CitationItem[] {
  const citations: CitationItem[] = [];
  const seen = new Set<string>();

  // Pattern 1: [Document: <name>, Page: <page>]
  const docPageRegex = /\[Document:\s*([^,\]]+),\s*Page:\s*(\d+)\]/gi;
  let match;
  while ((match = docPageRegex.exec(text)) !== null) {
    const key = `pdf:${match[1]}:${match[2]}`;
    if (!seen.has(key)) {
      seen.add(key);
      citations.push({
        type: "pdf",
        title: match[1].trim(),
        page: match[2],
        detail: `Page ${match[2]}`,
      });
    }
  }

  // Pattern 2: (Page X) or (Pages X-Y)
  const pageRegex = /\((?:Page|Pages)\s+(\d+(?:-\d+)?)\)/gi;
  while ((match = pageRegex.exec(text)) !== null) {
    const key = `page:${match[1]}`;
    if (!seen.has(key)) {
      seen.add(key);
      citations.push({
        type: "pdf",
        title: "Referenced Document",
        page: match[1],
        detail: `Page ${match[1]}`,
      });
    }
  }

  // Pattern 3: YouTube URLs
  const ytRegex = /(https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+))/gi;
  while ((match = ytRegex.exec(text)) !== null) {
    const key = `yt:${match[2]}`;
    if (!seen.has(key)) {
      seen.add(key);
      citations.push({
        type: "youtube",
        title: `YouTube Video (${match[2]})`,
        url: match[1],
        detail: "Video source",
      });
    }
  }

  // Pattern 4: GitHub Markdown links [file_path (lines X-Y)](https://github.com/...)
  const githubLinkRegex = /\[([^\]]+)\]\((https?:\/\/github\.com\/[^\s\)]+)\)/gi;
  while ((match = githubLinkRegex.exec(text)) !== null) {
    const key = `github:${match[2]}`;
    if (!seen.has(key)) {
      seen.add(key);
      const url = match[2];
      const lineMatch = url.match(/#L(\d+)(?:-L(\d+))?/i);
      let detail = "GitHub Source";
      if (lineMatch) {
        detail = lineMatch[2] ? `Lines ${lineMatch[1]}–${lineMatch[2]}` : `Line ${lineMatch[1]}`;
      }
      citations.push({
        type: "github",
        title: match[1].trim(),
        url: url,
        detail: detail,
      });
    }
  }

  // Pattern 5: Raw GitHub blob URLs with lines
  const rawGithubRegex = /(https?:\/\/github\.com\/[^\s\)]+\/blob\/[^\s\)]+#L\d+(?:-L\d+)?)/gi;
  while ((match = rawGithubRegex.exec(text)) !== null) {
    const url = match[1];
    const key = `github:${url}`;
    if (!seen.has(key)) {
      seen.add(key);
      const parts = url.split("/blob/")[1]?.split("#") || [];
      const filePath = parts[0] || "Code Source";
      const lineHash = parts[1] || "";
      const lineMatch = lineHash.match(/L(\d+)(?:-L(\d+))?/i);
      let detail = "GitHub Source";
      if (lineMatch) {
        detail = lineMatch[2] ? `Lines ${lineMatch[1]}–${lineMatch[2]}` : `Line ${lineMatch[1]}`;
      }
      citations.push({
        type: "github",
        title: filePath,
        url: url,
        detail: detail,
      });
    }
  }

  // Pattern 6: Web Markdown links [Title](https://...)
  const webLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/gi;
  while ((match = webLinkRegex.exec(text)) !== null) {
    if (!match[2].includes("youtube.com") && !match[2].includes("youtu.be") && !match[2].includes("github.com")) {
      const key = `web:${match[2]}`;
      if (!seen.has(key)) {
        seen.add(key);
        let detail = "Web Source";
        try {
          detail = new URL(match[2]).hostname;
        } catch {
          // ignore invalid URL
        }
        citations.push({
          type: "web",
          title: match[1],
          url: match[2],
          detail: detail,
        });
      }
    }
  }

  return citations;
}

export function SourceCitations({ content, threadId, onViewPdf }: SourceCitationsProps) {
  const [expanded, setExpanded] = useState(false);
  const citations = extractCitations(content);

  if (citations.length === 0) return null;

  return (
    <div className="mt-3 pt-2 border-t border-zinc-800/60 text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200 transition-colors font-medium mb-1.5"
      >
        <BookOpen className="h-3.5 w-3.5 text-pink-500" />
        <span>Grounded Sources & Citations ({citations.length})</span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </button>

      {expanded && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 animate-in fade-in-0 duration-150">
          {citations.map((item, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/80 border border-zinc-800/80 hover:border-zinc-700/80 transition-all text-zinc-300 group"
            >
              <div className="flex items-center gap-2 min-w-0 pr-2">
                {item.type === "pdf" && (
                  <FileText className="h-4 w-4 shrink-0 text-rose-400" />
                )}
                {item.type === "youtube" && (
                  <Youtube className="h-4 w-4 shrink-0 text-red-500" />
                )}
                {item.type === "web" && (
                  <Globe className="h-4 w-4 shrink-0 text-blue-400" />
                )}
                {item.type === "github" && (
                  <GitBranch className="h-4 w-4 shrink-0 text-emerald-400" />
                )}
                <div className="min-w-0">
                  <p className="truncate font-medium text-zinc-200">{item.title}</p>
                  {item.detail && (
                    <p className="text-[10px] text-zinc-400">{item.detail}</p>
                  )}
                </div>
              </div>

              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-pink-400 transition-colors"
                  title="Open source link"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : item.doc_id && onViewPdf ? (
                <button
                  onClick={() => onViewPdf(item.doc_id!, item.page)}
                  className="shrink-0 p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-pink-400 transition-colors"
                  title="View PDF page"
                >
                  <FileText className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

