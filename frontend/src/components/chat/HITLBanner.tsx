"use client";

import React, { useState } from "react";
import { AlertTriangle, Globe, XCircle, CheckCircle2, ShieldAlert } from "lucide-react";
import { Button } from "../ui/button";
import type { HITLInterruptData } from "../../types/chat";

interface HITLBannerProps {
  interrupt: HITLInterruptData;
  onResume: (decision: "yes" | "no") => Promise<void>;
}

export function HITLBanner({ interrupt, onResume }: HITLBannerProps) {
  const [submitting, setSubmitting] = useState<"yes" | "no" | null>(null);

  const promptText =
    interrupt?.question ||
    interrupt?.message ||
    "The agent could not find sufficient answer grounded in the uploaded documents. Do you approve executing a live web search to answer your question?";

  const handleDecision = async (decision: "yes" | "no") => {
    try {
      setSubmitting(decision);
      await onResume(decision);
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="mx-4 my-3 rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-amber-200 shadow-lg backdrop-blur-sm animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400">
          <ShieldAlert className="h-5 w-5" />
        </div>

        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-amber-300">
              Human-in-the-Loop Approval Required
            </h4>
            <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-300">
              CRAG Web Fallback
            </span>
          </div>

          <p className="text-xs text-amber-200/90 leading-relaxed">
            {promptText}
          </p>

          <div className="flex flex-wrap items-center gap-2.5 pt-1">
            <Button
              size="sm"
              variant="default"
              className="bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs shadow-sm shadow-amber-900/50"
              isLoading={submitting === "yes"}
              disabled={submitting !== null}
              onClick={() => handleDecision("yes")}
            >
              <Globe className="mr-1.5 h-3.5 w-3.5" />
              Approve Web Search
            </Button>

            <Button
              size="sm"
              variant="outline"
              className="border-zinc-700 bg-zinc-900/80 text-zinc-300 hover:bg-zinc-800 hover:text-white text-xs"
              isLoading={submitting === "no"}
              disabled={submitting !== null}
              onClick={() => handleDecision("no")}
            >
              <XCircle className="mr-1.5 h-3.5 w-3.5" />
              Decline (Answer with Available Context)
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

