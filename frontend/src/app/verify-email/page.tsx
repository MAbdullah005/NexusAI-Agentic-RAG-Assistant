"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, AlertCircle, ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "../../lib/api/client";

function VerifyEmailForm() {
  const searchParams = useSearchParams();
  const tokenFromUrl = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenFromUrl);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const doVerify = async (tokenToUse: string) => {
    if (!tokenToUse.trim()) {
      setError("Please provide a verification token.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const res = await api.verifyEmail(tokenToUse.trim());
      setSuccess(res.message || "Email verified successfully. You can now log in.");
    } catch (err: any) {
      setError(err?.message || "Failed to verify email. The token may be expired or invalid.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tokenFromUrl) {
      doVerify(tokenFromUrl);
    }
  }, [tokenFromUrl]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doVerify(token);
  };

  return (
    <div className="relative z-10 w-full max-w-md rounded-[32px] bg-white/80 backdrop-blur-2xl border border-white/90 p-8 sm:p-10 shadow-[0_25px_70px_-15px_rgba(168,85,247,0.18)]">
      <div className="h-11 w-11 rounded-2xl bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)] border border-slate-100 flex items-center justify-center mb-5 mx-auto">
        <ShieldCheck className="h-5 w-5 text-purple-600" />
      </div>

      <div className="text-center mb-6">
        <h3 className="text-2xl font-bold text-slate-900 tracking-tight">
          Verify Your Email
        </h3>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Confirm your email address to activate your NexusAI account
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2.5 rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-2.5 text-xs text-rose-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success ? (
        <div className="space-y-4 text-center py-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 border border-emerald-200 text-emerald-500">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            {success}
          </p>
          <Link
            href="/login"
            className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-[#d946ef] to-[#ec4899] text-white font-medium py-3 text-sm shadow-md transition-all hover:opacity-95"
          >
            Continue to Sign In
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block" htmlFor="token">
              Verification Token
            </label>
            <input
              id="token"
              type="text"
              placeholder="Paste verification token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              className="w-full rounded-full bg-slate-50/90 border border-slate-200/90 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-purple-400 focus:ring-4 focus:ring-purple-100/70 transition-all outline-none font-mono"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-full bg-gradient-to-r from-[#d946ef] via-[#ec4899] to-[#f43f5e] hover:opacity-95 text-white font-medium py-3 text-sm shadow-[0_8px_20px_-4px_rgba(236,72,153,0.4)] transition-all active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-2 mt-2"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              "Verify Email"
            )}
          </button>

          <div className="text-center pt-2">
            <Link
              href="/login"
              className="text-xs text-slate-500 hover:text-slate-900 font-medium"
            >
              Back to Sign In
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 md:p-8 bg-gradient-to-br from-[#dfd0ed] via-[#f7e1ee] to-[#d6e3f8] overflow-hidden">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-purple-300/50 blur-[100px]" />
        <div className="absolute top-1/2 -right-24 w-96 h-96 rounded-full bg-pink-300/50 blur-[100px]" />
        <div className="absolute -bottom-24 left-1/3 w-96 h-96 rounded-full bg-indigo-200/60 blur-[100px]" />
      </div>

      <Suspense fallback={<div className="text-slate-500 text-sm">Loading...</div>}>
        <VerifyEmailForm />
      </Suspense>
    </div>
  );
}
