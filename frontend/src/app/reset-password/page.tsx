"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { KeyRound, ArrowRight, ArrowLeft, AlertCircle, CheckCircle2, Lock, Eye, EyeOff } from "lucide-react";
import { api } from "../../lib/api/client";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tokenFromUrl = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenFromUrl);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!token.trim()) {
      setError("Reset token is missing. Please check your reset link.");
      return;
    }

    if (!newPassword || newPassword.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await api.resetPassword({
        token: token.trim(),
        new_password: newPassword,
      });
      setSuccess(res.message || "Password has been successfully reset.");
    } catch (err: any) {
      setError(err?.message || "Failed to reset password. The token may be expired or invalid.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative z-10 w-full max-w-md rounded-[32px] bg-white/80 backdrop-blur-2xl border border-white/90 p-8 sm:p-10 shadow-[0_25px_70px_-15px_rgba(168,85,247,0.18)]">
      <div className="h-11 w-11 rounded-2xl bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)] border border-slate-100 flex items-center justify-center mb-5 mx-auto">
        <KeyRound className="h-5 w-5 text-purple-600" />
      </div>

      <div className="text-center mb-6">
        <h3 className="text-2xl font-bold text-slate-900 tracking-tight">
          Create New Password
        </h3>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Enter your reset token and new secure password
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
            Sign In with New Password
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block" htmlFor="token">
              Reset Token
            </label>
            <input
              id="token"
              type="text"
              placeholder="Paste the reset token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              className="w-full rounded-full bg-slate-50/90 border border-slate-200/90 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-purple-400 focus:ring-4 focus:ring-purple-100/70 transition-all outline-none font-mono"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block" htmlFor="new-password">
              New Password
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                id="new-password"
                type={showPassword ? "text" : "password"}
                placeholder="•••••••• (min 6 chars)"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                required
                className="w-full rounded-full bg-slate-50/90 border border-slate-200/90 pl-11 pr-11 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-purple-400 focus:ring-4 focus:ring-purple-100/70 transition-all outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block" htmlFor="confirm-password">
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                id="confirm-password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
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
              "Save New Password"
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
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 md:p-8 bg-gradient-to-br from-[#dfd0ed] via-[#f7e1ee] to-[#d6e3f8] overflow-hidden">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-purple-300/50 blur-[100px]" />
        <div className="absolute top-1/2 -right-24 w-96 h-96 rounded-full bg-pink-300/50 blur-[100px]" />
        <div className="absolute -bottom-24 left-1/3 w-96 h-96 rounded-full bg-indigo-200/60 blur-[100px]" />
      </div>

      <Suspense fallback={<div className="text-slate-500 text-sm">Loading...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
