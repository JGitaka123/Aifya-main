"use client";

import type { ReactNode } from "react";
import { HeartPulse } from "lucide-react";
import { Link } from "@/i18n/routing";

/**
 * Visual shell for the /login and /sign-up pages.
 *
 * The left column is the approved Aifya auth artwork - a single static image
 * that already carries the brand mark, the promise chips, the headline and the
 * feature tiles. Nothing is layered on top of it, so the artwork and the page
 * can never overlap. The right column holds the live, translated form inside a
 * white card.
 */

export const AUTH_INPUT_CLASS =
  "h-10 w-full rounded-[8px] border border-[#DDE5EC] bg-white px-3 text-[13.5px] text-[#122A47] shadow-[0_1px_2px_rgba(16,42,67,0.05)] outline-none transition-all duration-150 placeholder:text-[#A4B3C0] focus:border-[#12A06F] focus:ring-[3px] focus:ring-[#12A06F]/15";

export const AUTH_LABEL_CLASS =
  "mb-1.5 block text-[12.5px] font-semibold text-[#4E6075]";

/**
 * Tinted block that groups a set of related fields, so the area to fill in
 * reads as a distinct grid rather than loose controls on the page.
 */
export const AUTH_PANEL_CLASS = "rounded-[12px] bg-[#F6F9FB] p-3.5";

/** Full-width heading row used above each grouped field set. */
export const AUTH_SECTION_TITLE_CLASS =
  "mb-3 flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-[0.08em] text-[#5A6B7D]";

/** White card that wraps the whole sign-in or registration form. */
export const AUTH_CARD_CLASS =
  "w-full max-w-[420px] rounded-[20px] border border-[#E3EBF1] bg-white p-5 shadow-[0_24px_60px_-32px_rgba(13,48,79,0.30)] sm:p-6";

/**
 * Shared style for the federated sign-in choices ("Continue with Google",
 * "Continue with Email") shown at the top of the login and sign-up forms.
 */
export const AUTH_SOCIAL_BUTTON_CLASS =
  "flex h-10 w-full items-center justify-start gap-3 rounded-[9px] border border-[#DEE6EC] bg-white pl-4 text-[13px] font-semibold text-[#13263E] shadow-[0_1px_2px_rgba(16,42,67,0.05)] transition-all duration-200 hover:-translate-y-0.5 hover:border-[#BFDAD3] hover:shadow-[0_8px_18px_-10px_rgba(16,42,67,0.25)]";

const TAB_GRADIENT =
  "bg-[linear-gradient(180deg,#16B96F_0%,#0B9B66_32%,#068A62_62%,#048B77_86%,#02929B_100%)]";

export function GoogleMark() {
  return (
    <svg aria-hidden className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47a5.57 5.57 0 0 1-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09A11.99 11.99 0 0 0 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29A7.2 7.2 0 0 1 4.89 12c0-.8.14-1.57.38-2.29V6.62H1.29a12.01 12.01 0 0 0 0 10.76l3.98-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.69 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  );
}

const VERTICAL_PHRASES = [
  "Your Data Safe",
  "Better Care",
  "Trusted Network",
  "Because You Matter",
];

function AuthTabs({ mode }: { mode: "login" | "signup" }) {
  const tabLink = (target: "login" | "signup", label: string) => (
    <Link
      href={`/${target}`}
      className={`flex h-9 items-center justify-center rounded-full text-[13px] transition-all duration-200 ${
        mode === target
          ? `${TAB_GRADIENT} font-bold text-white shadow-[0_10px_24px_-12px_rgba(9,138,98,0.55)]`
          : "font-semibold text-[#5D707C] hover:bg-white hover:text-[#16324A]"
      }`}
    >
      {label}
    </Link>
  );
  return (
    <div className="rounded-full border border-[#E2EAF0] bg-[#F1F5F8] p-1">
      <div className="grid grid-cols-2 gap-1.5">
        {tabLink("login", "Login")}
        {tabLink("signup", "Create Account")}
      </div>
    </div>
  );
}

function AuthMiniBrand() {
  return (
    <div className="flex items-center justify-center gap-3">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-[linear-gradient(150deg,#16B96F_0%,#0A9665_55%,#04715F_100%)] shadow-[0_10px_22px_-10px_rgba(9,138,98,0.55)]">
        <HeartPulse className="h-5 w-5 text-white" />
      </span>
      <span className="text-left">
        <span className="block text-[21px] font-extrabold leading-none tracking-tight text-[#0C413D]">
          Aifya
        </span>
        <span className="mt-0.5 block text-[11px] font-bold tracking-[0.02em] text-[#5E6E80]">
          Health System
        </span>
      </span>
    </div>
  );
}

/**
 * Full-page split layout shared by sign-in and facility registration.
 *
 * @param props.children - The auth column content rendered on the right
 * @returns The page shell around the auth card
 */
export default function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative isolate min-h-screen bg-[#F5F8FB] font-sans text-[#0C3054]">
      {/* Top-right "Health is Life" badge */}
      <div className="absolute right-6 top-6 z-20 hidden items-center gap-2 rounded-full border border-white/80 bg-white/80 px-3.5 py-1.5 shadow-[0_4px_16px_-8px_rgba(12,48,84,0.25)] backdrop-blur 2xl:flex">
        <HeartPulse className="h-3.5 w-3.5 text-[#0E6B58]" />
        <span className="text-[12.5px] font-bold text-[#0E5A4D]">
          Health is Life
        </span>
      </div>

      {/* Vertical brand rail (far right edge, clear of the card) */}
      <div
        aria-hidden
        className="absolute right-6 top-1/2 z-20 hidden -translate-y-1/2 flex-col items-center gap-9 2xl:flex"
      >
        {VERTICAL_PHRASES.map((phrase) => (
          <span
            key={phrase}
            className="flex items-center gap-3 text-[10.5px] font-bold uppercase tracking-[0.32em] text-[#2E8574]/80 [writing-mode:vertical-rl]"
          >
            <i className="h-1.5 w-1.5 rounded-full bg-[#2E8574]/70" />
            {phrase}
          </span>
        ))}
      </div>

      <main className="mx-auto grid min-h-screen w-full max-w-[1240px] grid-cols-1 items-stretch lg:grid-cols-[1.32fr_1fr]">
        {/* Hero artwork. Static image only - nothing is layered over it. */}
        <section className="relative hidden overflow-hidden lg:block">
          <img
            aria-hidden
            alt=""
            src="/auth/hero-art.jpg"
            className="pointer-events-none absolute inset-0 h-full w-full select-none object-cover object-left-top"
          />
        </section>

        <section className="flex items-center justify-center px-4 py-8 sm:px-6 lg:px-8">
          <div className={AUTH_CARD_CLASS}>{children}</div>
        </section>
      </main>
    </div>
  );
}

export { AuthMiniBrand, AuthTabs };