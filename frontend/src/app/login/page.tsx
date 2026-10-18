"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Lock, Eye, EyeOff, Sparkles, AlertCircle } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { Button } from "../../components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, loading: authLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.push("/");
    }
  }, [authLoading, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError("Please enter both email and password.");
      return;
    }

    try {
      setSubmitting(true);
      await login({ email: email.trim(), password });
      router.push("/");
    } catch (err: any) {
      setError(err?.message || "Failed to sign in. Please verify your credentials.");
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#E2D4F0] via-[#FCE7F3] to-[#DBEAFE]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 md:p-8 bg-gradient-to-br from-[#dfd0ed] via-[#f7e1ee] to-[#d6e3f8] overflow-hidden">
      {/* Ambient background blur circles */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-purple-300/50 blur-[100px]" />
        <div className="absolute top-1/2 -right-24 w-96 h-96 rounded-full bg-pink-300/50 blur-[100px]" />
        <div className="absolute -bottom-24 left-1/3 w-96 h-96 rounded-full bg-indigo-200/60 blur-[100px]" />
      </div>

      {/* Main card matching reference sample */}
      <div className="relative z-10 w-full max-w-[1020px] rounded-[36px] bg-white/70 backdrop-blur-2xl border border-white/80 shadow-[0_25px_70px_-15px_rgba(168,85,247,0.18)] p-4 md:p-6 flex flex-col md:flex-row gap-6">
        
        {/* Left Panel: Hero graphic & typography */}
        <div className="w-full md:w-1/2 rounded-[28px] p-8 md:p-10 flex flex-col justify-between relative overflow-hidden bg-gradient-to-br from-[#c4b5fd] via-[#f472b6] to-[#818cf8] shadow-inner min-h-[440px] md:min-h-[580px]">
          {/* Subtle glossy glass glow effects */}
          <div className="absolute -top-16 -right-16 w-56 h-56 rounded-full bg-white/20 blur-2xl pointer-events-none" />
          <div className="absolute -bottom-16 -left-16 w-56 h-56 rounded-full bg-purple-900/10 blur-2xl pointer-events-none" />

          {/* Large typography */}
          <div className="relative z-10">
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-black text-white/95 tracking-tight uppercase leading-none drop-shadow-sm">
              SMART AI
            </h1>
            <span className="text-xs sm:text-sm font-semibold tracking-widest text-white/80 uppercase block mt-1">
              Assistance
            </span>
          </div>

          {/* 3D Glassy Aesthetic Sphere */}
          <div className="relative my-auto flex items-center justify-center py-4">
            <div className="relative w-36 h-36 sm:w-44 sm:h-44 rounded-full shadow-[0_20px_50px_rgba(219,39,119,0.35)] backdrop-blur-md border border-white/50 overflow-hidden bg-gradient-to-br from-pink-300/90 via-purple-400/70 to-cyan-300/80 flex items-center justify-center">
              {/* Top reflection highlight */}
              <div className="absolute top-2 left-6 w-20 h-10 rounded-full bg-gradient-to-b from-white/95 to-transparent rotate-[-25deg] blur-[1px]" />
              {/* Inner ambient glow */}
              <div className="absolute bottom-1 right-2 w-28 h-20 rounded-full bg-cyan-300/70 blur-lg" />
              <div className="absolute inset-0 rounded-full bg-gradient-to-t from-purple-800/20 via-transparent to-white/20" />
            </div>
          </div>

          {/* Bottom title & description */}
          <div className="relative z-10 space-y-2 mt-4">
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
              Intelligent AI Assistance
            </h2>
            <p className="text-xs sm:text-sm text-slate-700/90 leading-relaxed max-w-sm">
              Experience smarter conversations with AI-powered responses, personalized insights & seamless productivity across every interaction.
            </p>
          </div>
        </div>

        {/* Right Panel: Centered Form & Social proof badge */}
        <div className="w-full md:w-1/2 flex flex-col justify-between gap-4">
          
          {/* Main Form Card */}
          <div className="rounded-[28px] bg-white/80 backdrop-blur-xl border border-white/90 p-7 sm:p-9 shadow-sm flex-1 flex flex-col justify-center">
            
            {/* Top brand icon */}
            <div className="h-11 w-11 rounded-2xl bg-white shadow-[0_2px_12px_rgba(0,0,0,0.06)] border border-slate-100 flex items-center justify-center mb-5">
              <Sparkles className="h-5 w-5 text-purple-600" />
            </div>

            <div className="mb-6">
              <h3 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                Welcome Back
              </h3>
              <p className="text-xs sm:text-sm text-slate-500 mt-1">
                Sign in to access your intelligent assistant
              </p>
            </div>

            {error && (
              <div className="mb-4 flex items-center gap-2.5 rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-2.5 text-xs text-rose-600 animate-in fade-in-0 duration-150">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block" htmlFor="email">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    required
                    className="w-full rounded-full bg-slate-50/90 border border-slate-200/90 pl-11 pr-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-purple-400 focus:ring-4 focus:ring-purple-100/70 transition-all outline-none"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block" htmlFor="password">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
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

              {/* Remember Me & Forgot Password */}
              <div className="flex items-center justify-between pt-0.5">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded-md border-slate-300 text-pink-500 focus:ring-pink-400 cursor-pointer"
                  />
                  <span className="text-xs text-slate-600 font-normal">Remember me</span>
                </label>

                <Link
                  href="/forgot-password"
                  className="text-xs font-medium text-slate-600 hover:text-slate-900 hover:underline transition-colors"
                >
                  Forgot Password?
                </Link>
              </div>

              {/* Sign In Button */}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-full bg-gradient-to-r from-[#d946ef] via-[#ec4899] to-[#f43f5e] hover:opacity-95 text-white font-medium py-3 text-sm shadow-[0_8px_20px_-4px_rgba(236,72,153,0.4)] transition-all active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
              >
                {submitting ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            <p className="text-center text-xs text-slate-500 mt-6">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="font-semibold text-slate-900 hover:underline">
                Sign up
              </Link>
            </p>
          </div>

          {/* Bottom Social Proof Card */}
          <div className="rounded-[22px] bg-white/80 backdrop-blur-md border border-white/90 px-6 py-3.5 flex items-center gap-3.5 shadow-sm">
            <div className="flex -space-x-2.5 overflow-hidden">
              <div className="inline-flex h-8 w-8 items-center justify-center rounded-full ring-2 ring-white bg-gradient-to-tr from-purple-400 to-indigo-300 text-[11px] font-bold text-white shadow-xs">
                AK
              </div>
              <div className="inline-flex h-8 w-8 items-center justify-center rounded-full ring-2 ring-white bg-gradient-to-tr from-pink-400 to-rose-300 text-[11px] font-bold text-white shadow-xs">
                SL
              </div>
              <div className="inline-flex h-8 w-8 items-center justify-center rounded-full ring-2 ring-white bg-gradient-to-tr from-cyan-400 to-blue-300 text-[11px] font-bold text-white shadow-xs">
                MR
              </div>
            </div>
            <div>
              <p className="text-xs font-bold text-slate-900 leading-tight">10 Million+ Users</p>
              <p className="text-[10px] text-slate-500 leading-tight">worldwide</p>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
