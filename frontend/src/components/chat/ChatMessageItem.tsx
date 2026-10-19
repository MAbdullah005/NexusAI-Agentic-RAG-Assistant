"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Check, Copy, Sparkles } from "lucide-react";
import { cn, formatTimestamp } from "../../lib/utils";
import { SourceCitations } from "./SourceCitations";
import type { ChatMessage } from "../../types/chat";

interface ChatMessageItemProps {
  message: ChatMessage;
  threadId?: string;
  onViewPdf?: (docId: string, page?: number | string) => void;
  theme?: "light" | "dark";
}

function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const codeText = String(children).replace(/\n$/, "");

  const handleCopy = () => {
    navigator.clipboard.writeText(codeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-3 rounded-xl border border-pink-100 dark:border-zinc-800 bg-[#0d0e15] overflow-hidden group">
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900/60 border-b border-zinc-800/80 text-[11px] text-zinc-400">
        <span>{className?.replace(/language-/, "") || "code"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] hover:bg-zinc-800 text-zinc-400 hover:text-pink-300 transition-colors"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="p-3.5 overflow-x-auto text-xs text-zinc-200 font-mono">
        <code>{children}</code>
      </div>
    </div>
  );
}

export function ChatMessageItem({ message, threadId, onViewPdf, theme = "light" }: ChatMessageItemProps) {
  const isUser = message.role === "user";
  const isLight = theme === "light";

  return (
    <div
      className={cn(
        "group flex w-full gap-3 px-4 py-3 transition-colors",
        isUser
          ? "justify-end"
          : isLight
          ? "justify-start bg-pink-50/20"
          : "justify-start bg-zinc-950/40"
      )}
    >
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-xl overflow-hidden shadow-xs mt-0.5 border border-pink-200/70 dark:border-white/10 bg-white dark:bg-zinc-900 p-0.5">
          <img
            src="/nexus-logo.png"
            alt="NexusAI"
            className="h-7 w-7 object-contain rounded-lg"
          />
        </div>
      )}

      <div
        className={cn(
          "relative max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-xs transition-colors",
          isUser
            ? "bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-br-sm shadow-pink-500/15"
            : isLight
            ? "border border-pink-100 bg-white text-slate-800 rounded-bl-sm shadow-[0_2px_12px_rgba(244,114,182,0.06)]"
            : "border border-zinc-800/80 bg-zinc-900/70 text-zinc-200 rounded-bl-sm backdrop-blur-sm"
        )}
      >
        {message.pending ? (
          <div className="flex items-center gap-2.5 py-1 text-pink-500 dark:text-pink-400">
            <Sparkles className="h-4 w-4 animate-spin text-pink-500" />
            <span className="text-xs">Thinking & retrieving grounded sources...</span>
          </div>
        ) : (
          <>
            <div className={cn(
              "prose max-w-none prose-p:leading-relaxed prose-pre:p-0 prose-pre:bg-transparent text-sm",
              isUser ? "prose-invert" : isLight ? "prose-slate" : "prose-invert"
            )}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const isInline = !match && !String(children).includes("\n");
                    if (isInline) {
                      return (
                        <code
                          className={cn(
                            "rounded px-1.5 py-0.5 text-xs font-mono font-medium",
                            isLight
                              ? "bg-pink-50 text-pink-700 border border-pink-100"
                              : "bg-zinc-800/80 text-pink-300"
                          )}
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    }
                    return (
                      <CodeBlock className={className}>
                        {children}
                      </CodeBlock>
                    );
                  },
                  a({ href, children }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-pink-600 dark:text-pink-400 underline underline-offset-2 hover:text-pink-700 font-medium"
                      >
                        {children}
                      </a>
                    );
                  },
                  table({ children }) {
                    return (
                      <div className="my-2 w-full overflow-x-auto rounded-lg border border-pink-100 dark:border-zinc-800">
                        <table className="w-full text-left text-xs">{children}</table>
                      </div>
                    );
                  },
                  th({ children }) {
                    return (
                      <th className={cn(
                        "border-b px-3 py-2 font-semibold text-xs",
                        isLight
                          ? "border-pink-100 bg-pink-50/60 text-slate-800"
                          : "border-zinc-800 bg-zinc-900/90 text-zinc-200"
                      )}>
                        {children}
                      </th>
                    );
                  },
                  td({ children }) {
                    return (
                      <td className={cn(
                        "border-b px-3 py-2 text-xs",
                        isLight
                          ? "border-pink-100/50 text-slate-700"
                          : "border-zinc-800/50 text-zinc-300"
                      )}>
                        {children}
                      </td>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>

            {/* Citations section for Assistant responses */}
            {!isUser && (
              <SourceCitations
                content={message.content}
                threadId={threadId}
                onViewPdf={onViewPdf}
              />
            )}
          </>
        )}

        {message.createdAt && (
          <div
            className={cn(
              "mt-1 text-[10px] select-none text-right opacity-60",
              isUser ? "text-pink-100" : isLight ? "text-slate-400" : "text-zinc-500"
            )}
          >
            {formatTimestamp(message.createdAt)}
          </div>
        )}
      </div>
    </div>
  );
}
