"use client";

import { type FormEvent, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import AuthShell, {
  AuthMiniBrand,
  AuthTabs,
  AUTH_INPUT_CLASS,
  AUTH_PANEL_CLASS,
  AUTH_SOCIAL_BUTTON_CLASS,
  GoogleMark,
} from "@/components/auth/AuthShell";

const PRIMARY_BUTTON_CLASS =
  "flex h-11 w-full items-center justify-center rounded-[10px] bg-[linear-gradient(180deg,#12B568_0%,#0A9A65_30%,#068A63_62%,#048B78_86%,#019299_100%)] text-[13.5px] font-bold text-white shadow-[0_10px_20px_-10px_rgba(6,128,86,0.55)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_14px_26px_-10px_rgba(6,128,86,0.65)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:translate-y-0";

/**
 * Sign-in page: hero column on the left, the plain auth form column on the
 * right with the Login / Create Account segmented switch. Credentials are
 * verified by Aifya's own backend through the /api/auth/login BFF, which
 * keeps the session tokens in httpOnly cookies.
 *
 * @returns The sign-in page
 */
export default function LoginPage() {
  const t = useTranslations("auth");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  const focusEmail = () => {
    setNotice(null);
    emailRef.current?.focus();
  };

  const handleGoogleSignIn = () => {
    setError(null);
    setNotice(t("googleNotConnected"));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        error?: string;
        user?: { name?: string };
      };
      if (!response.ok) {
        setError(data.error ?? "Invalid email or password.");
        return;
      }
      const returnTo =
        new URLSearchParams(window.location.search).get("returnTo") ?? "/";
      window.location.assign(returnTo);
    } catch {
      setError("Could not reach the sign-in service. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <AuthMiniBrand />

      <div className="mt-4 text-center">
        <h2 className="text-[21px] font-extrabold tracking-tight text-[#15345A]">
          Welcome Back!
        </h2>
        <p className="mt-1 text-[12.5px] font-medium text-[#66788B]">
          Sign in to your account to continue
        </p>
      </div>

      <div className="mt-4">
        <AuthTabs mode="login" />
      </div>

      <div className="mt-4 space-y-2.5">
        <button
          type="button"
          onClick={handleGoogleSignIn}
          className={AUTH_SOCIAL_BUTTON_CLASS}
        >
          <GoogleMark />
          {t("continueWithGoogle")}
        </button>
        <button
          type="button"
          onClick={focusEmail}
          className={AUTH_SOCIAL_BUTTON_CLASS}
        >
          <Mail className="h-4 w-4 text-[#0F8B6D]" />
          {t("continueWithEmail")}
        </button>
      </div>

      {notice && (
        <p className="mt-3 rounded-[10px] border border-[#E7D9BC] bg-[#FDF6E9] px-3.5 py-2.5 text-[12.5px] font-medium leading-relaxed text-[#92610B]">
          {notice}
        </p>
      )}

      <div className="my-3.5 flex items-center gap-4">
        <span className="h-px flex-1 bg-[#E4EAF0]" />
        <span className="text-[10.5px] font-extrabold tracking-[0.18em] text-[#9AA9B6]">
          OR
        </span>
        <span className="h-px flex-1 bg-[#E4EAF0]" />
      </div>

      <form onSubmit={handleSubmit} className={AUTH_PANEL_CLASS}>
        <div className="grid grid-cols-1 gap-3">
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#93A7B6]" />
            <input
              id="email"
              type="email"
              name="email"
              ref={emailRef}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              aria-label="Email address"
              placeholder="Email address"
              className={`${AUTH_INPUT_CLASS} pl-10 placeholder:font-medium placeholder:text-[#6E7E90]`}
            />
          </div>

          <div className="relative">
            <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#93A7B6]" />
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              name="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              aria-label="Password"
              placeholder="Password"
              className={`${AUTH_INPUT_CLASS} pl-10 pr-10 placeholder:font-medium placeholder:text-[#6E7E90]`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-[#93A7B6] transition-colors hover:text-[#0B8F79]"
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>

          {forgotOpen && (
            <p className="flex items-start gap-1.5 text-xs leading-relaxed text-[#6B7B8D]">
              Contact your facility administrator to reset your password.
            </p>
          )}

          <div className="flex items-center justify-between">
            <label className="flex cursor-pointer select-none items-center gap-2 text-[13px] font-semibold text-[#54677B]">
              <input
                type="checkbox"
                checked={remember}
                onChange={(event) => setRemember(event.target.checked)}
                className="h-[17px] w-[17px] rounded accent-[#0B8F79]"
              />
              Remember me
            </label>
            <button
              type="button"
              onClick={() => setForgotOpen((open) => !open)}
              className="text-[13px] font-bold text-[#0F8B6D] transition-colors hover:text-[#05614C]"
            >
              Forgot password?
            </button>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-[10px] border border-[#FECDD3] bg-[#FFF1F2] px-3.5 py-2.5 text-[13px] font-semibold text-[#BE123C]"
            >
              {error}
            </div>
          )}

          <button type="submit" disabled={submitting} className={PRIMARY_BUTTON_CLASS}>
            {submitting ? "Signing In..." : "Sign In"}
          </button>
        </div>
      </form>

      <p className="mt-4 text-center text-[12.5px] font-medium text-[#64768A]">
        Don&apos;t have an account?{" "}
        <Link
          href="/signup"
          className="font-extrabold text-[#0F8B6D] underline-offset-4 transition-colors hover:text-[#05614C] hover:underline"
        >
          Create one
        </Link>
      </p>
    </AuthShell>
  );
}