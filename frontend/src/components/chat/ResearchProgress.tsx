"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Search,
  BookOpen,
  FileText,
  Filter,
  FileCheck,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Globe,
  Loader2,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { ResearchStageUpdate, ResearchSource } from "../../types/chat";

interface ResearchProgressProps {
  update: ResearchStageUpdate;
  theme?: "light" | "dark";
}

const STAGES = [
  { key: "planning", label: "Plan", icon: Sparkles },
  { key: "searching", label: "Search", icon: Search },
  { key: "extracting", label: "Extract", icon: Globe },
  { key: "filtering", label: "Filter", icon: Filter },
  { key: "generating", label: "Synthesize", icon: FileCheck },
];

export function ResearchProgress({ update, theme = "light" }: ResearchProgressProps) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isLight = theme === "light";

  const { stage, stage_message, sub_queries = [], sources = [], evidence_count } = update;

  // Determine stage index
  const stageIndexMap: Record<string, number> = {
    planning: 0,
    searching: 1,
    extracting: 2,
    filtering: 3,
    generating: 4,
    completed: 5,
  };
  const currentIndex = stageIndexMap[stage] ?? 0;

  // Categorize sources
  const webSources = sources.filter((s) => s.source_type === "web");
  const arxivSources = sources.filter((s) => s.source_type === "arxiv");
  const docSources = sources.filter((s) => s.source_type === "document");

  return (
    <div
      className={cn(
        "my-3 w-full max-w-3xl rounded-2xl border p-4 sm:p-5 shadow-sm transition-all animate-in fade-in-50 duration-300",
        isLight
          ? "border-rose-200/80 bg-white/95 text-slate-800 shadow-[0_4px_20px_-4px_rgba(244,63,94,0.12)]"
          : "border-rose-900/40 bg-zinc-950/80 text-zinc-200 shadow-xl"
      )}
    >
      {/* Header with Title and Current Status */}
      <div className="flex items-center justify-between gap-3 border-b pb-3 mb-3 border-rose-100 dark:border-zinc-800/80">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-rose-500 to-pink-500 text-white shadow-sm shadow-rose-500/30">
            {stage === "completed" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
          </div>
          <div>
            <h4 className="text-sm font-bold flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
              <span>Deep Research Investigation</span>
              <span className="text-[10px] font-normal uppercase tracking-wider px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300">
                {stage}
              </span>
            </h4>
            <p className="text-xs text-slate-500 dark:text-zinc-400 line-clamp-1">
              {stage_message || "Investigating research query across multi-source evidence..."}
            </p>
          </div>
        </div>

        {sources.length > 0 && (
          <button
            type="button"
            onClick={() => setSourcesOpen(!sourcesOpen)}
            className={cn(
              "flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border transition-colors",
              isLight
                ? "border-slate-200 hover:bg-slate-50 text-slate-600"
                : "border-zinc-800 hover:bg-zinc-900 text-zinc-300"
            )}
          >
            <span>{sources.length} sources</span>
            {sourcesOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>

      {/* Stepper Bar */}
      <div className="grid grid-cols-5 gap-1 sm:gap-2 mb-3">
        {STAGES.map((st, idx) => {
          const Icon = st.icon;
          const isDone = currentIndex > idx;
          const isCurrent = currentIndex === idx;

          return (
            <div
              key={st.key}
              className={cn(
                "flex flex-col items-center justify-center py-1.5 px-1 rounded-lg text-center transition-all",
                isDone
                  ? isLight
                    ? "bg-rose-50 text-rose-600"
                    : "bg-rose-950/40 text-rose-300"
                  : isCurrent
                  ? "bg-rose-500 text-white font-medium shadow-xs"
                  : isLight
                  ? "bg-slate-50 text-slate-400"
                  : "bg-zinc-900/40 text-zinc-600"
              )}
            >
              <Icon className="h-3.5 w-3.5 mb-0.5" />
              <span className="text-[10px] hidden sm:inline">{st.label}</span>
            </div>
          );
        })}
      </div>

      {/* Sub-queries Pills (if generated) */}
      {sub_queries.length > 0 && (
        <div className="space-y-1.5 mb-3">
          <span className="text-[11px] font-semibold text-slate-500 dark:text-zinc-400">
            Targeted Research Angles:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {sub_queries.map((sq, i) => (
              <span
                key={i}
                className={cn(
                  "text-[11px] px-2 py-0.5 rounded-md border",
                  isLight
                    ? "border-slate-200 bg-slate-50 text-slate-700"
                    : "border-zinc-800 bg-zinc-900/60 text-zinc-300"
                )}
              >
                {sq}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Evidence Stats Pills */}
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-zinc-400">
        {webSources.length > 0 && (
          <span className="flex items-center gap-1">
            <Globe className="h-3 w-3 text-sky-500" />
            <span>{webSources.length} Web</span>
          </span>
        )}
        {arxivSources.length > 0 && (
          <span className="flex items-center gap-1">
            <BookOpen className="h-3 w-3 text-amber-500" />
            <span>{arxivSources.length} arXiv papers</span>
          </span>
        )}
        {docSources.length > 0 && (
          <span className="flex items-center gap-1">
            <FileText className="h-3 w-3 text-emerald-500" />
            <span>{docSources.length} Attached docs</span>
          </span>
        )}
        {typeof evidence_count === "number" && evidence_count > 0 && (
          <span className="flex items-center gap-1 ml-auto font-medium text-rose-600 dark:text-rose-400">
            <Filter className="h-3 w-3" />
            <span>{evidence_count} evidence chunks curated</span>
          </span>
        )}
      </div>

      {/* Expandable Sources Drawer */}
      {sourcesOpen && sources.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-100 dark:border-zinc-800 max-h-48 overflow-y-auto space-y-1.5 text-xs">
          {sources.map((s, idx) => (
            <div
              key={idx}
              className={cn(
                "flex items-center justify-between gap-2 p-1.5 rounded-lg border",
                isLight
                  ? "border-slate-100 bg-slate-50/50 hover:bg-slate-50 text-slate-700"
                  : "border-zinc-850 bg-zinc-900/40 hover:bg-zinc-900 text-zinc-300"
              )}
            >
              <div className="flex items-center gap-2 min-w-0">
                {s.source_type === "arxiv" ? (
                  <BookOpen className="h-3.5 w-3.5 shrink-0 text-amber-500" />
                ) : s.source_type === "document" ? (
                  <FileText className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                ) : (
                  <Globe className="h-3.5 w-3.5 shrink-0 text-sky-500" />
                )}
                <span className="truncate text-[11px] font-medium">{s.title || s.url}</span>
              </div>
              {s.url && s.url.startsWith("http") && (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-slate-400 hover:text-rose-500 dark:hover:text-rose-400 p-1"
                >
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

