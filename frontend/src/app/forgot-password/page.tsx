"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Mail, Sparkles, AlertCircle, CheckCircle2, ArrowRight, ArrowLeft } from "lucide-react";
import { api } from "../../lib/api/client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await api.forgotPassword(email.trim());
      setSuccessMessage(
        res.message || "If the email exists, a password reset link has been sent."
      );
    } catch (err: any) {
      setError(err?.message || "Failed to process request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 md:p-8 bg-gradient-to-br from-[#dfd0ed] via-[#f7e1ee] to-[#d6e3f8] overflow-hidden">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-purple-300/50 blur-[100px]" />
        <div className="absolute top-1/2 -right-24 w-96 h-96 rounded-full bg-pink-300/50 blur-[100px]" />
        <div className="absolute -bottom-24 left-1/3 w-96 h-96 rounded-full bg-indigo-200/60 blur-[100px]" />
      </div>

      <div className="relative z-10 w-full max-w-md rounded-[32px] bg-white/80 backdrop-blur-2xl border border-white/90 p-8 sm:p-10 shadow-[0_25px_70px_-15px_rgba(168,85,247,0.18)]">
        <div className="h-11 w-11 rounded-2xl bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)] border border-slate-100 flex items-center justify-center mb-5 mx-auto">
          <Mail className="h-5 w-5 text-purple-600" />
        </div>

        <div className="text-center mb-6">
          <h3 className="text-2xl font-bold text-slate-900 tracking-tight">
            Reset Password
          </h3>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Enter your email and we will send you a reset link
          </p>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2.5 rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-2.5 text-xs text-rose-600">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage ? (
          <div className="space-y-4 text-center py-2">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 border border-emerald-200 text-emerald-500">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              {successMessage}
            </p>
            <Link
              href="/login"
              className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-[#d946ef] to-[#ec4899] text-white font-medium py-3 text-sm shadow-md transition-all hover:opacity-95"
            >
              Return to Sign In
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 block" htmlFor="email">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="email"
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  className="w-full rounded-full bg-slate-50/90 border border-slate-200/90 pl-11 pr-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-purple-400 focus:ring-4 focus:ring-purple-100/70 transition-all outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-full bg-gradient-to-r from-[#d946ef] via-[#ec4899] to-[#f43f5e] hover:opacity-95 text-white font-medium py-3 text-sm shadow-[0_8px_20px_-4px_rgba(236,72,153,0.4)] transition-all active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-2 mt-2"
            >
              {submitting ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                "Send Reset Link"
              )}
            </button>

            <div className="text-center pt-2">
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 font-medium"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Sign In
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
