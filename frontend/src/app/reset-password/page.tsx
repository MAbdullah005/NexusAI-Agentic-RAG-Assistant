"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { KeyRound, ArrowRight, ArrowLeft, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "../../lib/api/client";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../../components/ui/card";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tokenFromUrl = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenFromUrl);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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
    <Card className="w-full max-w-md border-zinc-800/80 bg-zinc-950/80 backdrop-blur-xl shadow-2xl relative z-10">
      <CardHeader className="space-y-2 text-center pb-6">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-400 mb-2">
          <KeyRound className="h-6 w-6" />
        </div>
        <CardTitle className="text-2xl font-bold tracking-tight text-white">
          Set New Password
        </CardTitle>
        <CardDescription className="text-zinc-400">
          Enter your new password below to regain access to your account
        </CardDescription>
      </CardHeader>

      {success ? (
        <CardContent className="space-y-6 text-center py-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <CheckCircle2 className="h-7 w-7" />
          </div>
          <div className="space-y-2">
            <h4 className="text-base font-semibold text-zinc-100">Password Updated</h4>
            <p className="text-sm text-zinc-400 leading-relaxed">
              {success}
            </p>
          </div>
          <div className="pt-2">
            <Link href="/login">
              <Button className="w-full">
                Proceed to Sign In
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </CardContent>
      ) : (
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-400 animate-in fade-in-0 duration-150">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {!tokenFromUrl && (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300" htmlFor="token">
                  Reset Token
                </label>
                <Input
                  id="token"
                  type="text"
                  placeholder="Paste reset token from email"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-zinc-300" htmlFor="new-password">
                New Password
              </label>
              <Input
                id="new-password"
                type="password"
                placeholder="Enter at least 6 characters"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-zinc-300" htmlFor="confirm-new-password">
                Confirm New Password
              </label>
              <Input
                id="confirm-new-password"
                type="password"
                placeholder="Re-enter new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>
          </CardContent>

          <CardFooter className="flex flex-col space-y-3 pt-2">
            <Button
              type="submit"
              className="w-full font-semibold group"
              isLoading={submitting}
            >
              Update Password
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Button>

            <div className="pt-2">
              <Link
                href="/login"
                className="inline-flex items-center text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
                Cancel and return to login
              </Link>
            </div>
          </CardFooter>
        </form>
      )}
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#090a0f] p-4 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none" />
      <Suspense fallback={<div className="text-zinc-400 text-sm">Loading reset form...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}

