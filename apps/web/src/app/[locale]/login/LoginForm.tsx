"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { Building2, Eye, EyeOff, Lock, Mail } from "lucide-react";
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
 * Human-readable text for the error codes the Keycloak callback puts on the
 * URL. The callback deliberately reports short codes rather than prose so the
 * wording can live here, next to the screen that shows it.
 */
const AUTH_ERROR_MESSAGES: Record<string, string> = {
  cancelled: "Sign-in was cancelled. You can try again when you are ready.",
  invalid_state:
    "That sign-in attempt could not be verified. Please start again.",
  session_expired: "The sign-in attempt timed out. Please start again.",
  exchange_failed:
    "We could not complete the sign-in with your account provider. Please try again.",
  provider_error:
    "Your account provider reported a problem. Please try again, or contact your administrator.",
};

const DEFAULT_AUTH_ERROR = "Sign-in could not be completed. Please try again.";

/** How a refused sign-in is worded on the screen. */
interface SignInAlert {
  /** Headline, e.g. "Access Denied". Omitted for plain failures. */
  title?: string;
  /** The sentence the person actually needs to read. */
  body: string;
  /** Warning styling for the repeat wording. */
  tone?: "error" | "warning";
}

/** Session key counting refused sign-ins, so the wording can escalate. */
const UNREGISTERED_ATTEMPTS_KEY = "aifya.unregisteredSignInAttempts";

/**
 * How many times an unregistered sign-in has been refused in this session.
 *
 * @returns The stored count, or 0 when storage is unavailable
 */
function readRefusedAttempts(): number {
  try {
    const stored = window.sessionStorage.getItem(UNREGISTERED_ATTEMPTS_KEY);
    return Number(stored ?? 0) || 0;
  } catch {
    return 0;
  }
}

/**
 * Record another refused sign-in and report the running total.
 *
 * @returns The count including this attempt
 */
function rememberRefusedAttempt(): number {
  const attempts = readRefusedAttempts() + 1;
  try {
    window.sessionStorage.setItem(UNREGISTERED_ATTEMPTS_KEY, String(attempts));
  } catch {
    // Storage disabled: the count still holds for this page view.
  }
  return attempts;
}

/** Forget the refusal count once somebody signs in. */
function clearRefusedAttempts(): void {
  try {
    window.sessionStorage.removeItem(UNREGISTERED_ATTEMPTS_KEY);
  } catch {
    // Nothing stored, nothing to clear.
  }
}

interface LoginFormProps {
  /** True when the deployment signs users in through Keycloak. */
  keycloakEnabled: boolean;
}

/**
 * Sign-in form: hero column on the left, the plain auth form column on the
 * right with the Login / Register-facility segmented switch.
 *
 * With AUTH_PROVIDER=internal the credentials are verified by Aifya's own
 * backend through the /api/auth/login BFF, which keeps the session tokens in
 * httpOnly cookies. With AUTH_PROVIDER=keycloak the button hands the browser
 * to Keycloak instead: the hospital's identity provider checks the password,
 * so this form never sees it.
 *
 * @param props - Which provider is in force
 * @returns The sign-in page contents
 */
export default function LoginForm({ keycloakEnabled }: LoginFormProps) {
  const t = useTranslations("auth");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [forgotOpen, setForgotOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [facility, setFacility] = useState("");
  const [alert, setAlert] = useState<SignInAlert | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  // Read the failure code the OIDC callback redirected back with. Done in an
  // effect rather than during render so the server render stays identical to
  // the first client render.
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("error");
    if (code) {
      setAlert({ body: AUTH_ERROR_MESSAGES[code] ?? DEFAULT_AUTH_ERROR });
    }
  }, []);

  const focusEmail = () => {
    setNotice(null);
    emailRef.current?.focus();
  };

  const handleGoogleSignIn = () => {
    setAlert(null);
    setNotice(t("googleNotConnected"));
  };

  const startKeycloakSignIn = () => {
    const returnTo =
      new URLSearchParams(window.location.search).get("returnTo") ?? "/";
    window.location.assign(
      `/api/auth/login?returnTo=${encodeURIComponent(returnTo)}`,
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAlert(null);
    setNotice(null);
    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        // The hospital travels with the credentials so the API can match it
        // against the employee's HR record: a valid password still must not
        // open the wrong hospital's data.
        body: JSON.stringify({ email, password, facility }),
      });
      const data = (await response.json().catch(() => ({}))) as {
        error?: string;
        code?: string | null;
        user?: { name?: string };
      };
      if (!response.ok) {
        if (data.code === "not_registered") {
          // Being told "not registered" once is information; being told it again
          // is a dead end, so the second refusal stops repeating it and names
          // exactly what to ask HR to do.
          if (rememberRefusedAttempt() > 1) {
            setAlert({
              tone: "warning",
              title: t("hrAssistanceTitle"),
              body: t("hrAssistanceBody"),
            });
          } else {
            setAlert({
              title: t("accessDeniedTitle"),
              body: t("notRegisteredBody"),
            });
          }
          return;
        }
        if (data.code === "access_revoked") {
          setAlert({
            title: t("accessDeniedTitle"),
            body: t("accessRevokedBody"),
          });
          return;
        }
        if (data.code === "facility_mismatch") {
          // The password was right but the hospital was not. The API explains
          // which name to check, so the message travels through unchanged.
          setAlert({
            title: t("accessDeniedTitle"),
            body: data.error ?? t("invalidCredentials"),
          });
          return;
        }
        setAlert({ body: data.error ?? t("invalidCredentials") });
        return;
      }
      clearRefusedAttempts();
      const returnTo =
        new URLSearchParams(window.location.search).get("returnTo") ?? "/";
      window.location.assign(returnTo);
    } catch {
      setAlert({ body: t("serviceUnreachable") });
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

      {!keycloakEnabled && (
        <>
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
        </>
      )}

      {keycloakEnabled ? (
        <div className={`mt-4 ${AUTH_PANEL_CLASS}`}>
          <div className="grid grid-cols-1 gap-3">
            {alert && (
              <div
                role="alert"
                className={
                  alert.tone === "warning"
                    ? "rounded-[10px] border border-[#FDE68A] bg-[#FFFBEB] px-3.5 py-2.5 text-[13px] text-[#92400E]"
                    : "rounded-[10px] border border-[#FECDD3] bg-[#FFF1F2] px-3.5 py-2.5 text-[13px] text-[#BE123C]"
                }
              >
                {alert.title && (
                  <p className="mb-0.5 font-extrabold">{alert.title}</p>
                )}
                <p className="font-semibold">{alert.body}</p>
              </div>
            )}

            <button
              type="button"
              onClick={startKeycloakSignIn}
              className={PRIMARY_BUTTON_CLASS}
            >
              Continue with your hospital account
            </button>

            <p className="text-center text-[12.5px] font-medium leading-relaxed text-[#6B7B8D]">
              You will be taken to your facility&apos;s secure sign-in page to
              enter your password.
            </p>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className={AUTH_PANEL_CLASS}>
          <div className="grid grid-cols-1 gap-3">
            <div className="relative">
              <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#93A7B6]" />
              <input
                id="facility"
                type="text"
                name="facility"
                value={facility}
                onChange={(event) => setFacility(event.target.value)}
                autoComplete="organization"
                aria-label="Hospital name"
                placeholder="Hospital name"
                required
                className={`${AUTH_INPUT_CLASS} pl-10 placeholder:font-medium placeholder:text-[#6E7E90]`}
              />
            </div>

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
                {t("forgotPasswordHint")}
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

            {alert && (
              <div
                role="alert"
                className={
                  alert.tone === "warning"
                    ? "rounded-[10px] border border-[#FDE68A] bg-[#FFFBEB] px-3.5 py-2.5 text-[13px] text-[#92400E]"
                    : "rounded-[10px] border border-[#FECDD3] bg-[#FFF1F2] px-3.5 py-2.5 text-[13px] text-[#BE123C]"
                }
              >
                {alert.title && (
                  <p className="mb-0.5 font-extrabold">{alert.title}</p>
                )}
                <p className="font-semibold">{alert.body}</p>
              </div>
            )}

            <button type="submit" disabled={submitting} className={PRIMARY_BUTTON_CLASS}>
              {submitting ? "Signing In..." : "Sign In"}
            </button>
          </div>
        </form>
      )}

      <p className="mt-4 text-center text-[12.5px] font-medium text-[#64768A]">
        {t("noAccount")}{" "}
        <Link
          href="/signup"
          className="font-extrabold text-[#0F8B6D] underline-offset-4 transition-colors hover:text-[#05614C] hover:underline"
        >
          {t("registerFacility")}
        </Link>
      </p>
    </AuthShell>
  );
}
