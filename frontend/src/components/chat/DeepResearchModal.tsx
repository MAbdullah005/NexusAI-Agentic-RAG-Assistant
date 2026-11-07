"use client";

import React, { useState, useEffect } from "react";
import { Sparkles, Sliders, BookOpen, Layers, Check, RotateCcw } from "lucide-react";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../ui/dialog";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";
import type { DeepResearchConfig } from "../../types/chat";

interface DeepResearchModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  config: DeepResearchConfig;
  onSaveConfig: (newConfig: DeepResearchConfig) => void;
  theme?: "light" | "dark";
}

const DEFAULT_CONFIG: DeepResearchConfig = {
  search_count: 10,
  report_length: "long",
  citation_style: "APA",
  subqueries_count: 3,
  iterations: 1,
  instructions: "",
};

export function DeepResearchModal({
  open,
  onOpenChange,
  config,
  onSaveConfig,
  theme = "light",
}: DeepResearchModalProps) {
  const [localConfig, setLocalConfig] = useState<DeepResearchConfig>({ ...DEFAULT_CONFIG, ...config });

  useEffect(() => {
    setLocalConfig({ ...DEFAULT_CONFIG, ...config });
  }, [config, open]);

  const handleSave = () => {
    onSaveConfig(localConfig);
    onOpenChange(false);
  };

  const handleReset = () => {
    setLocalConfig(DEFAULT_CONFIG);
  };

  const isLight = theme === "light";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <div className={cn("space-y-5", isLight ? "text-slate-800" : "text-zinc-100")}>
        <DialogHeader>
          <div className="flex items-center gap-2 text-rose-500 dark:text-rose-400">
            <Sparkles className="h-5 w-5" />
            <DialogTitle className={cn("text-lg font-bold", isLight ? "text-slate-900" : "text-zinc-100")}>
              Deep Research Configuration
            </DialogTitle>
          </div>
          <DialogDescription className={cn("text-xs", isLight ? "text-slate-500" : "text-zinc-400")}>
            Customize the autonomous research workflow, target length, and citation format.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-xs">
          {/* Report Depth / Length */}
          <div className="space-y-2">
            <label className="font-semibold block flex items-center justify-between">
              <span>Report Depth</span>
              <span className="text-[11px] font-normal text-slate-400 dark:text-zinc-500">
                {localConfig.report_length === "short"
                  ? "~1,000 words"
                  : localConfig.report_length === "medium"
                  ? "~2,000 words"
                  : "~3,500+ words"}
              </span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "short", label: "Executive", desc: "Key findings" },
                { id: "medium", label: "Standard", desc: "Detailed breakdown" },
                { id: "long", label: "Comprehensive", desc: "Exhaustive deep dive" },
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setLocalConfig((prev) => ({ ...prev, report_length: opt.id as any }))}
                  className={cn(
                    "flex flex-col items-start p-2.5 rounded-lg border text-left transition-all",
                    localConfig.report_length === opt.id
                      ? "border-rose-500 bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold ring-1 ring-rose-500"
                      : isLight
                      ? "border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700"
                      : "border-zinc-800 hover:border-zinc-700 bg-zinc-900/50 text-zinc-300"
                  )}
                >
                  <span className="text-xs">{opt.label}</span>
                  <span className="text-[10px] opacity-70 font-normal">{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Citation Format */}
          <div className="space-y-2">
            <label className="font-semibold block">Academic Citation Style</label>
            <div className="grid grid-cols-3 gap-2">
              {(["APA", "MLA", "Harvard"] as const).map((style) => (
                <button
                  key={style}
                  type="button"
                  onClick={() => setLocalConfig((prev) => ({ ...prev, citation_style: style }))}
                  className={cn(
                    "flex items-center justify-center py-2 px-3 rounded-lg border text-xs transition-all",
                    localConfig.citation_style === style
                      ? "border-rose-500 bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold ring-1 ring-rose-500"
                      : isLight
                      ? "border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700"
                      : "border-zinc-800 hover:border-zinc-700 bg-zinc-900/50 text-zinc-300"
                  )}
                >
                  <span>{style} 7th</span>
                </button>
              ))}
            </div>
          </div>

          {/* Search Scope & Sub-Queries */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="font-semibold block">Target Sources</label>
              <select
                value={localConfig.search_count}
                onChange={(e) => setLocalConfig((prev) => ({ ...prev, search_count: Number(e.target.value) }))}
                className={cn(
                  "w-full rounded-lg border px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-rose-500",
                  isLight
                    ? "border-slate-200 bg-white text-slate-800"
                    : "border-zinc-800 bg-zinc-900 text-zinc-200"
                )}
              >
                <option value={5}>5 Sources (Fastest)</option>
                <option value={10}>10 Sources (Balanced)</option>
                <option value={15}>15 Sources (In-depth)</option>
                <option value={20}>20 Sources (Maximum)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold block">Research Sub-Queries</label>
              <select
                value={localConfig.subqueries_count}
                onChange={(e) => setLocalConfig((prev) => ({ ...prev, subqueries_count: Number(e.target.value) }))}
                className={cn(
                  "w-full rounded-lg border px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-rose-500",
                  isLight
                    ? "border-slate-200 bg-white text-slate-800"
                    : "border-zinc-800 bg-zinc-900 text-zinc-200"
                )}
              >
                <option value={2}>2 Focused Angles</option>
                <option value={3}>3 Angles (Recommended)</option>
                <option value={4}>4 Comprehensive Angles</option>
                <option value={5}>5 Angles (Broadest)</option>
              </select>
            </div>
          </div>

          {/* Custom Research Directives */}
          <div className="space-y-1.5">
            <label className="font-semibold block">Custom Focus & Directives (Optional)</label>
            <textarea
              rows={3}
              value={localConfig.instructions || ""}
              onChange={(e) => setLocalConfig((prev) => ({ ...prev, instructions: e.target.value }))}
              placeholder="e.g., Emphasize benchmark figures, compare performance vs alternatives, include architecture diagrams in ASCII/Mermaid..."
              className={cn(
                "w-full rounded-lg border p-2.5 text-xs focus:outline-none focus:ring-1 focus:ring-rose-500 resize-none",
                isLight
                  ? "border-slate-200 bg-white text-slate-800 placeholder:text-slate-400"
                  : "border-zinc-800 bg-zinc-900 text-zinc-200 placeholder:text-zinc-500"
              )}
            />
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between sm:justify-between pt-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className={cn("text-xs gap-1.5", isLight ? "text-slate-500" : "text-zinc-400")}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset Defaults</span>
          </Button>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleSave}
              className="text-xs bg-gradient-to-r from-rose-500 to-pink-600 hover:from-rose-600 hover:to-pink-700 text-white"
            >
              Save Configuration
            </Button>
          </div>
        </DialogFooter>
      </div>
    </Dialog>
  );
}

