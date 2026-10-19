"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  Sparkles,
  AlertCircle,
  Sun,
  Moon,
  Phone,
  Info,
  Check,
  Copy,
  ArrowRight,
  BookOpen,
  Compass,
  MessageSquare,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, loading: authLoading } = useAuth();

  // Form states
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Theme state: light by default
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Copy status indicators
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [copiedPhone, setCopiedPhone] = useState(false);

  // Email input reference to focus when "Sign In" is clicked
  const emailInputRef = useRef<HTMLInputElement>(null);

  // Initialize theme from localStorage if user previously toggled it, otherwise light by default
  useEffect(() => {
    const savedTheme = localStorage.getItem("nexus_auth_theme") as "light" | "dark" | null;
    if (savedTheme === "dark" || savedTheme === "light") {
      setTheme(savedTheme);
      if (savedTheme === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    } else {
      setTheme("light");
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    localStorage.setItem("nexus_auth_theme", nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

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

  // Smooth scroll helpers for top navigation
  const scrollToSection = (sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleSignInNavClick = () => {
    const el = document.getElementById("signin");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    setTimeout(() => {
      emailInputRef.current?.focus();
    }, 400);
  };

  const copyToClipboard = (text: string, type: "email" | "phone") => {
    navigator.clipboard.writeText(text);
    if (type === "email") {
      setCopiedEmail(true);
      setTimeout(() => setCopiedEmail(false), 2000);
    } else {
      setCopiedPhone(true);
      setTimeout(() => setCopiedPhone(false), 2000);
    }
  };

  const isDark = theme === "dark";

  if (authLoading) {
    return (
      <div
        className={`flex min-h-screen items-center justify-center transition-colors ${
          isDark
            ? "bg-[#0c0d14]"
            : "bg-gradient-to-br from-[#dfd0ed] via-[#f7e1ee] to-[#d6e3f8]"
        }`}
      >
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-pink-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div
      className={`min-h-screen w-full flex flex-col justify-between transition-colors duration-300 relative overflow-x-hidden ${
        isDark
          ? "bg-[#0b0c16] text-white"
          : "bg-gradient-to-br from-[#dfd0ed] via-[#f7e1ee] to-[#d6e3f8] text-slate-900"
      }`}
    >
      {/* Ambient decorative blur orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div
          className={`absolute -top-32 -left-32 w-[550px] h-[550px] rounded-full blur-[130px] transition-all duration-500 ${
            isDark ? "bg-purple-900/25" : "bg-purple-300/50"
          }`}
        />
        <div
          className={`absolute top-1/3 -right-32 w-[550px] h-[550px] rounded-full blur-[130px] transition-all duration-500 ${
            isDark ? "bg-pink-950/20" : "bg-pink-300/50"
          }`}
        />
        <div
          className={`absolute -bottom-32 left-1/3 w-[550px] h-[550px] rounded-full blur-[130px] transition-all duration-500 ${
            isDark ? "bg-indigo-950/30" : "bg-indigo-200/60"
          }`}
        />
      </div>

      {/* STICKY TOP NAVIGATION BAR */}
      <header className="sticky top-0 z-30 w-full px-4 sm:px-8 lg:px-12 py-3 sm:py-4">
        <div
          className={`mx-auto w-full max-w-7xl rounded-2xl px-4 sm:px-6 py-3 flex items-center justify-between backdrop-blur-xl border transition-all duration-300 shadow-sm ${
            isDark
              ? "bg-[#141523]/80 border-white/10 shadow-[0_8px_30px_rgba(0,0,0,0.5)]"
              : "bg-white/70 border-white/80 shadow-[0_4px_20px_rgba(244,114,182,0.1)]"
          }`}
        >
          {/* Logo & Brand title */}
          <div className="flex items-center gap-3">
            <img
              src="/nexus-logo.png"
              alt="Nexus AI Logo"
              className="h-9 w-9 object-contain rounded-xl shadow-sm ring-1 ring-white/50"
            />
            <div className="flex flex-col">
              <span className="font-extrabold text-base sm:text-lg tracking-tight bg-gradient-to-r from-pink-500 via-rose-500 to-purple-600 bg-clip-text text-transparent">
                Nexus AI
              </span>
              <span className="text-[10px] font-medium tracking-wider uppercase text-slate-500 dark:text-zinc-400 -mt-1">
                Assistance
              </span>
            </div>
          </div>

          {/* Top Actions: Exactly 4 buttons (About, Contacts, Sign In, Register) + Theme Toggle */}
          <div className="flex items-center gap-1 sm:gap-2 md:gap-3">
            {/* Button 1: About (smooth scrolls to #about) */}
            <button
              type="button"
              onClick={() => scrollToSection("about")}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm font-medium transition-all ${
                isDark
                  ? "text-zinc-300 hover:text-white hover:bg-white/10"
                  : "text-slate-700 hover:text-pink-600 hover:bg-pink-50/60"
              }`}
            >
              About
            </button>

            {/* Button 2: Contacts (smooth scrolls to #contacts) */}
            <button
              type="button"
              onClick={() => scrollToSection("contacts")}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm font-medium transition-all ${
                isDark
                  ? "text-zinc-300 hover:text-white hover:bg-white/10"
                  : "text-slate-700 hover:text-pink-600 hover:bg-pink-50/60"
              }`}
            >
              Contacts
            </button>

            {/* Button 3: Sign In (smooth scrolls to #signin) */}
            <button
              type="button"
              onClick={handleSignInNavClick}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm font-semibold transition-all ${
                isDark
                  ? "text-pink-300 bg-pink-500/10 border border-pink-500/20 hover:bg-pink-500/20"
                  : "text-pink-700 bg-pink-100/80 border border-pink-200/80 hover:bg-pink-100"
              }`}
            >
              Sign In
            </button>

            {/* Button 4: Register (navigates to /signup) */}
            <Link
              href="/signup"
              className="px-3.5 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm font-medium bg-gradient-to-r from-pink-500 to-rose-500 text-white shadow-sm hover:opacity-95 transition-all active:scale-[0.98]"
            >
              Register
            </Link>

            {/* Theme Toggle Button (Light mode default) */}
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle Theme"
              className={`ml-1 p-2 rounded-full transition-all border ${
                isDark
                  ? "bg-zinc-800/80 border-zinc-700 text-amber-300 hover:bg-zinc-700"
                  : "bg-white/90 border-pink-200/80 text-slate-700 hover:text-pink-600 hover:bg-white shadow-xs"
              }`}
              title={isDark ? "Switch to Light Theme" : "Switch to Light Theme"}
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* FULL-SCREEN SPLIT HERO: Branding & Login Form */}
      <main className="relative z-10 flex-1 w-full max-w-7xl mx-auto px-4 sm:px-8 lg:px-12 py-3 lg:py-6 flex flex-col lg:flex-row items-stretch justify-center gap-6 lg:gap-8">
        
        {/* LEFT PANEL: Nexus AI Branding, 3D Artwork, and New Slogan */}
        <div
          className={`w-full lg:w-1/2 rounded-[32px] p-8 sm:p-10 lg:p-12 flex flex-col justify-between relative overflow-hidden transition-all duration-300 shadow-2xl min-h-[460px] lg:min-h-[600px] ${
            isDark
              ? "bg-gradient-to-br from-[#1d1238] via-[#3b1259] to-[#121530] border border-white/10"
              : "bg-gradient-to-br from-[#c4b5fd] via-[#f472b6] to-[#818cf8] shadow-inner"
          }`}
        >
          {/* Glass reflections & glow highlights */}
          <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full bg-white/20 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-16 -left-16 w-64 h-64 rounded-full bg-purple-900/20 blur-3xl pointer-events-none" />

          {/* Top Branding Section */}
          <div className="relative z-10">
            <div className="flex items-center gap-4 sm:gap-5">
              <img
                src="/nexus-logo.png"
                alt="Nexus AI Emblem"
                className="h-14 w-14 sm:h-16 sm:w-16 object-contain rounded-2xl shadow-xl ring-2 ring-white/40 bg-white/15 backdrop-blur-md p-1.5 shrink-0"
              />
              <div className="flex flex-col">
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight uppercase leading-none drop-shadow-sm">
                  Nexus AI
                </h1>
                <div className="mt-2 self-start">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs sm:text-sm font-bold tracking-widest uppercase bg-white/25 text-white backdrop-blur-md border border-white/40 shadow-sm">
                    Assistance
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 3D Glassy Aesthetic Sphere & Visual centerpiece */}
          <div className="relative my-auto flex items-center justify-center py-6">
            <div className="relative w-44 h-44 sm:w-52 sm:h-52 rounded-full shadow-[0_25px_60px_rgba(219,39,119,0.35)] backdrop-blur-md border border-white/50 overflow-hidden bg-gradient-to-br from-pink-300/90 via-purple-400/70 to-cyan-300/80 flex items-center justify-center animate-pulse duration-3000">
              {/* Top reflection highlight */}
              <div className="absolute top-3 left-8 w-24 h-12 rounded-full bg-gradient-to-b from-white/95 to-transparent rotate-[-25deg] blur-[1px]" />
              {/* Inner ambient glow */}
              <div className="absolute bottom-2 right-3 w-32 h-24 rounded-full bg-cyan-300/75 blur-lg" />
              <div className="absolute inset-0 rounded-full bg-gradient-to-t from-purple-900/20 via-transparent to-white/25" />
            </div>
          </div>

          {/* Bottom Headline & Subtitle per prompt instructions */}
          <div className="relative z-10 space-y-2">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight drop-shadow-xs">
              One place for knowledge. Endless possibilities.
            </h2>
            <p className="text-xs sm:text-sm text-white/90 leading-relaxed max-w-md font-medium">
              Ask questions, explore your sources, and uncover meaningful insights
            </p>
          </div>
        </div>

        {/* RIGHT PANEL: Centered Login Form with id="signin" */}
        <div id="signin" className="w-full lg:w-1/2 flex items-center justify-center">
          <div
            className={`w-full max-w-xl rounded-[32px] p-8 sm:p-10 lg:p-12 transition-all duration-300 backdrop-blur-2xl border shadow-2xl flex flex-col justify-center ${
              isDark
                ? "bg-[#141525]/90 border-white/10 shadow-[0_20px_60px_rgba(0,0,0,0.6)]"
                : "bg-white/85 border-white/90 shadow-[0_25px_70px_-15px_rgba(244,114,182,0.18)]"
            }`}
          >
            {/* Form Top Sparkle Icon */}
            <div
              className={`h-12 w-12 rounded-2xl flex items-center justify-center mb-6 shadow-sm border ${
                isDark
                  ? "bg-[#1f2038] border-pink-500/30 text-pink-400"
                  : "bg-white border-pink-100 text-pink-600 shadow-[0_2px_12px_rgba(244,114,182,0.1)]"
              }`}
            >
              <Sparkles className="h-6 w-6" />
            </div>

            {/* Form Header */}
            <div className="mb-6">
              <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                Welcome Back
              </h3>
              <p
                className={`text-xs sm:text-sm mt-1.5 ${
                  isDark ? "text-zinc-400" : "text-slate-500"
                }`}
              >
                Sign in to access your intelligent Nexus AI workspace
              </p>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mb-5 flex items-center gap-2.5 rounded-2xl border border-rose-200 bg-rose-50/90 dark:bg-rose-950/40 dark:border-rose-900/50 px-4 py-3 text-xs text-rose-600 dark:text-rose-300 animate-in fade-in-0 duration-150">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Form Inputs */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div className="space-y-1.5">
                <label
                  className={`text-xs font-semibold block ${
                    isDark ? "text-zinc-300" : "text-slate-700"
                  }`}
                  htmlFor="email"
                >
                  Email
                </label>
                <div className="relative">
                  <Mail
                    className={`absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 ${
                      isDark ? "text-zinc-500" : "text-slate-400"
                    }`}
                  />
                  <input
                    ref={emailInputRef}
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    required
                    className={`w-full rounded-full pl-11 pr-4 py-3 text-sm transition-all outline-none border ${
                      isDark
                        ? "bg-[#1c1d32] border-white/10 text-white placeholder:text-zinc-500 focus:border-pink-400 focus:ring-4 focus:ring-pink-900/40"
                        : "bg-slate-50/90 border-pink-100 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-pink-400 focus:ring-4 focus:ring-pink-100/70"
                    }`}
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label
                  className={`text-xs font-semibold block ${
                    isDark ? "text-zinc-300" : "text-slate-700"
                  }`}
                  htmlFor="password"
                >
                  Password
                </label>
                <div className="relative">
                  <Lock
                    className={`absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 ${
                      isDark ? "text-zinc-500" : "text-slate-400"
                    }`}
                  />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    className={`w-full rounded-full pl-11 pr-11 py-3 text-sm transition-all outline-none border ${
                      isDark
                        ? "bg-[#1c1d32] border-white/10 text-white placeholder:text-zinc-500 focus:border-pink-400 focus:ring-4 focus:ring-pink-900/40"
                        : "bg-slate-50/90 border-pink-100 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-pink-400 focus:ring-4 focus:ring-pink-100/70"
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className={`absolute right-4 top-1/2 -translate-y-1/2 transition-colors ${
                      isDark ? "text-zinc-500 hover:text-zinc-300" : "text-slate-400 hover:text-slate-600"
                    }`}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Remember Me & Forgot Password */}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded-md border-slate-300 text-pink-500 focus:ring-pink-400 cursor-pointer"
                  />
                  <span
                    className={`text-xs ${
                      isDark ? "text-zinc-400" : "text-slate-600"
                    }`}
                  >
                    Remember me
                  </span>
                </label>

                <Link
                  href="/forgot-password"
                  className={`text-xs font-medium hover:underline transition-colors ${
                    isDark ? "text-pink-400 hover:text-pink-300" : "text-slate-600 hover:text-pink-600"
                  }`}
                >
                  Forgot Password?
                </Link>
              </div>

              {/* Sign In Button */}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-full bg-gradient-to-r from-pink-500 via-rose-500 to-pink-600 hover:opacity-95 text-white font-semibold py-3.5 text-sm shadow-[0_8px_25px_-4px_rgba(236,72,153,0.45)] transition-all active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-4"
              >
                {submitting ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <>
                    Sign In
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            {/* Bottom Register Redirect */}
            <p
              className={`text-center text-xs mt-6 ${
                isDark ? "text-zinc-400" : "text-slate-500"
              }`}
            >
              Don&apos;t have an account?{" "}
              <Link
                href="/signup"
                className={`font-semibold hover:underline ${
                  isDark ? "text-pink-400" : "text-pink-600"
                }`}
              >
                Register
              </Link>
            </p>
          </div>
        </div>

      </main>

      {/* ON-PAGE SECTION: ABOUT (id="about") */}
      <section
        id="about"
        className="relative z-10 w-full max-w-7xl mx-auto px-4 sm:px-8 lg:px-12 py-12 scroll-mt-20"
      >
        <div
          className={`rounded-[32px] p-8 sm:p-12 backdrop-blur-2xl border transition-all duration-300 shadow-xl ${
            isDark
              ? "bg-[#141525]/80 border-white/10"
              : "bg-white/80 border-white/90 shadow-[0_20px_50px_rgba(244,114,182,0.12)]"
          }`}
        >
          <div className="max-w-3xl mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-pink-500/10 text-pink-600 dark:text-pink-400 border border-pink-500/20 mb-3">
              <Info className="h-3.5 w-3.5" />
              <span>About Nexus AI</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              One place for knowledge. Endless possibilities.
            </h2>
            <p className={`mt-2 text-sm sm:text-base leading-relaxed ${isDark ? "text-zinc-400" : "text-slate-600"}`}>
              NexusAI connects your knowledge sources with conversational AI to provide grounded answers, clear summaries, and seamless workflows.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div
              className={`p-6 rounded-2xl border transition-all ${
                isDark
                  ? "bg-white/5 border-white/5 hover:border-pink-500/30"
                  : "bg-pink-50/40 border-pink-100 hover:border-pink-200"
              }`}
            >
              <div className="h-10 w-10 rounded-xl bg-pink-500/10 text-pink-500 flex items-center justify-center mb-4">
                <BookOpen className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold mb-1.5">Multi-Source Grounding</h3>
              <p className={`text-xs sm:text-sm leading-relaxed ${isDark ? "text-zinc-400" : "text-slate-600"}`}>
                Effortlessly upload documents, analyze PDF pages, review YouTube video transcripts, and consult web articles.
              </p>
            </div>

            <div
              className={`p-6 rounded-2xl border transition-all ${
                isDark
                  ? "bg-white/5 border-white/5 hover:border-pink-500/30"
                  : "bg-pink-50/40 border-pink-100 hover:border-pink-200"
              }`}
            >
              <div className="h-10 w-10 rounded-xl bg-pink-500/10 text-pink-500 flex items-center justify-center mb-4">
                <Compass className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold mb-1.5">Grounded Answers</h3>
              <p className={`text-xs sm:text-sm leading-relaxed ${isDark ? "text-zinc-400" : "text-slate-600"}`}>
                Receive accurate, transparent answers cited directly from your uploaded materials with verifiable references.
              </p>
            </div>

            <div
              className={`p-6 rounded-2xl border transition-all ${
                isDark
                  ? "bg-white/5 border-white/5 hover:border-pink-500/30"
                  : "bg-pink-50/40 border-pink-100 hover:border-pink-200"
              }`}
            >
              <div className="h-10 w-10 rounded-xl bg-pink-500/10 text-pink-500 flex items-center justify-center mb-4">
                <MessageSquare className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold mb-1.5">Natural Conversations</h3>
              <p className={`text-xs sm:text-sm leading-relaxed ${isDark ? "text-zinc-400" : "text-slate-600"}`}>
                Ask natural questions, manage multiple chat threads, and resume previous discussions with persistent history.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ON-PAGE SECTION: CONTACTS (id="contacts") */}
      <section
        id="contacts"
        className="relative z-10 w-full max-w-7xl mx-auto px-4 sm:px-8 lg:px-12 py-12 scroll-mt-20"
      >
        <div
          className={`rounded-[32px] p-8 sm:p-12 backdrop-blur-2xl border transition-all duration-300 shadow-xl ${
            isDark
              ? "bg-[#141525]/80 border-white/10"
              : "bg-white/80 border-white/90 shadow-[0_20px_50px_rgba(244,114,182,0.12)]"
          }`}
        >
          <div className="max-w-2xl mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-pink-500/10 text-pink-600 dark:text-pink-400 border border-pink-500/20 mb-3">
              <Phone className="h-3.5 w-3.5" />
              <span>Contact Information</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
              Get in Touch
            </h2>
            <p className={`mt-2 text-sm sm:text-base leading-relaxed ${isDark ? "text-zinc-400" : "text-slate-600"}`}>
              Reach out directly for inquiries, technical assistance, or collaboration.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 max-w-3xl">
            {/* Phone Card */}
            <div
              className={`p-5 rounded-2xl border flex items-center justify-between transition-all ${
                isDark
                  ? "bg-white/5 border-white/10 hover:border-pink-500/30"
                  : "bg-slate-50/90 border-pink-100 hover:border-pink-200"
              }`}
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <div className="p-3 rounded-xl bg-pink-500/10 text-pink-500 shrink-0">
                  <Phone className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className={`text-xs font-medium ${isDark ? "text-zinc-400" : "text-slate-500"}`}>
                    Phone Number
                  </p>
                  <a
                    href="tel:+923134039492"
                    className="text-sm sm:text-base font-bold hover:text-pink-600 transition-colors block truncate"
                  >
                    +92 3134039492
                  </a>
                </div>
              </div>
              <button
                type="button"
                onClick={() => copyToClipboard("+92 3134039492", "phone")}
                className={`p-2.5 rounded-xl text-xs font-medium transition-colors ${
                  copiedPhone
                    ? "text-emerald-500 bg-emerald-500/10"
                    : isDark
                    ? "text-zinc-400 hover:text-white hover:bg-white/10"
                    : "text-slate-500 hover:text-pink-600 hover:bg-pink-100/60"
                }`}
                title="Copy Phone Number"
              >
                {copiedPhone ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>

            {/* Email Card */}
            <div
              className={`p-5 rounded-2xl border flex items-center justify-between transition-all ${
                isDark
                  ? "bg-white/5 border-white/10 hover:border-pink-500/30"
                  : "bg-slate-50/90 border-pink-100 hover:border-pink-200"
              }`}
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <div className="p-3 rounded-xl bg-pink-500/10 text-pink-500 shrink-0">
                  <Mail className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className={`text-xs font-medium ${isDark ? "text-zinc-400" : "text-slate-500"}`}>
                    Email Address
                  </p>
                  <a
                    href="mailto:abdullahaliofc@gmail.com"
                    className="text-sm sm:text-base font-bold hover:text-pink-600 transition-colors block truncate"
                  >
                    abdullahaliofc@gmail.com
                  </a>
                </div>
              </div>
              <button
                type="button"
                onClick={() => copyToClipboard("abdullahaliofc@gmail.com", "email")}
                className={`p-2.5 rounded-xl text-xs font-medium transition-colors ${
                  copiedEmail
                    ? "text-emerald-500 bg-emerald-500/10"
                    : isDark
                    ? "text-zinc-400 hover:text-white hover:bg-white/10"
                    : "text-slate-500 hover:text-pink-600 hover:bg-pink-100/60"
                }`}
                title="Copy Email Address"
              >
                {copiedEmail ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="relative z-10 w-full px-6 py-6 text-center border-t border-black/5 dark:border-white/5">
        <p className={`text-xs ${isDark ? "text-zinc-500" : "text-slate-500"}`}>
          © {new Date().getFullYear()} Nexus AI. All rights reserved.
        </p>
      </footer>

    </div>
  );
}
