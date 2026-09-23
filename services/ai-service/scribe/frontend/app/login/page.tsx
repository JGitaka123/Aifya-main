"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/Toast";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { login } = useAuth();
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/";
  const isMockMode = process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";

  const handleMockLogin = async () => {
    setEmail("dr.smith@aifya.com");
    setPassword("anypassword");
    setIsSubmitting(true);
    try {
      await login("dr.smith@aifya.com", "anypassword");
      toast("Mock login successful!", "success");
      router.push(redirectTo);
    } catch (err: any) {
      toast("Mock login failed", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    setIsSubmitting(true);
    try {
      await login(email, password);
      toast("Welcome back!", "success");
      router.push(redirectTo);
    } catch (err: any) {
      toast(err.message || "Login failed. Please check your credentials.", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[70vh]">
      <div className="w-full max-w-md">
        <div className="card overflow-hidden shadow-lg">
          <div className="bg-medical-blue px-8 py-6 text-white text-center">
            <h1 className="text-2xl font-bold">AIFYA</h1>
            <p className="text-sm opacity-80 mt-1">Health Platform Sign In</p>
          </div>

          <form onSubmit={handleSubmit} className="p-8 space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="doctor@maryhelphospital.org"
                required
                autoComplete="email"
                className="input w-full"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  className="input w-full pr-16"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 text-xs font-medium transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "HIDE" : "SHOW"}
                </button>
              </div>
            </div>

            {redirectTo !== "/" && (
              <p className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 rounded-md border border-amber-100 dark:border-amber-900/30">
                You&apos;ll be redirected to your requested page after signing in.
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting || !email || !password}
              className="w-full py-2.5 bg-medical-blue text-white font-medium rounded-lg hover:bg-medical-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </button>

            {isMockMode && (
              <div className="pt-4 border-t dark:border-slate-700 mt-4">
                <button
                  type="button"
                  onClick={handleMockLogin}
                  disabled={isSubmitting}
                  className="w-full py-2 bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 border border-emerald-600/20 dark:border-emerald-600/40 font-medium rounded-lg hover:bg-emerald-600/20 transition-colors flex items-center justify-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Quick Mock Login
                </button>
                <p className="text-[10px] text-center text-slate-400 mt-2 italic">
                  Available because NEXT_PUBLIC_USE_MOCK_DATA is enabled
                </p>
              </div>
            )}
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 dark:text-slate-500 mt-4">
          Contact your facility administrator for account access.
        </p>
      </div>
    </div>
  );
}
