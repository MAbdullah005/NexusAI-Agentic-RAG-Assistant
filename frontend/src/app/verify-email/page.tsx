"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, AlertCircle, ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "../../lib/api/client";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../../components/ui/card";

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
    <Card className="w-full max-w-md border-zinc-800/80 bg-zinc-950/80 backdrop-blur-xl shadow-2xl relative z-10">
      <CardHeader className="space-y-2 text-center pb-6">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-400 mb-2">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <CardTitle className="text-2xl font-bold tracking-tight text-white">
          Verify Your Email
        </CardTitle>
        <CardDescription className="text-zinc-400">
          Confirm your email address to activate your NexusAI account
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {loading && (
          <div className="flex flex-col items-center justify-center py-6 space-y-3">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            <p className="text-sm text-zinc-400">Verifying your token...</p>
          </div>
        )}

        {success && (
          <div className="space-y-6 text-center py-4">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <CheckCircle2 className="h-7 w-7" />
            </div>
            <div className="space-y-2">
              <h4 className="text-base font-semibold text-zinc-100">Verification Complete</h4>
              <p className="text-sm text-zinc-400 leading-relaxed">
                {success}
              </p>
            </div>
            <div className="pt-2">
              <Link href="/login">
                <Button className="w-full">
                  Sign In to NexusAI
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="space-y-4">
            <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-400">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300" htmlFor="manual-token">
                  Or enter token manually:
                </label>
                <Input
                  id="manual-token"
                  type="text"
                  placeholder="Paste verification token"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" isLoading={loading}>
                Retry Verification
              </Button>
            </form>
          </div>
        )}

        {!tokenFromUrl && !loading && !success && !error && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-zinc-300" htmlFor="verify-token">
                Verification Token
              </label>
              <Input
                id="verify-token"
                type="text"
                placeholder="Paste the verification token from your email"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full font-semibold" isLoading={loading}>
              Verify Token
            </Button>
          </form>
        )}
      </CardContent>

      <CardFooter className="flex justify-center border-t border-zinc-800/80 pt-4">
        <Link
          href="/login"
          className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          Return to Sign In
        </Link>
      </CardFooter>
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#090a0f] p-4 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none" />
      <Suspense fallback={<div className="text-zinc-400 text-sm">Loading verification...</div>}>
        <VerifyEmailForm />
      </Suspense>
    </div>
  );
}

