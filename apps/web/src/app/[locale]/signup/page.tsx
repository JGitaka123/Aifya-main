"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "@/i18n/routing";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Lock,
  Mail,
  Sparkles,
} from "lucide-react";
import AuthShell, {
  AuthMiniBrand,
  AuthTabs,
  AUTH_INPUT_CLASS,
  AUTH_LABEL_CLASS,
  AUTH_PANEL_CLASS,
  AUTH_SECTION_TITLE_CLASS,
  AUTH_SOCIAL_BUTTON_CLASS,
  GoogleMark,
} from "@/components/auth/AuthShell";
import { useFacilitySignup } from "@/hooks/useOnboarding";

const signupSchema = z
  .object({
    facility_name: z.string().min(2).max(200),
    facility_type: z.enum(["hospital", "clinic", "dispensary", "health_centre"]),
    county: z.string().max(100).optional().or(z.literal("")),
    mfl_code: z.string().max(20).optional().or(z.literal("")),
    facility_phone: z
      .string()
      .refine(
        (value) =>
          !value || /^(?:\+?254|0)?[17]\d{8}$/.test(value.replace(/[\s-]/g, "")),
        { message: "Enter a valid Kenyan phone number" },
      )
      .optional()
      .or(z.literal("")),
    admin_first_name: z.string().min(1).max(100),
    admin_last_name: z.string().min(1).max(100),
    admin_email: z.string().email().max(255),
    admin_password: z.string().min(8, { message: "Use at least 8 characters." }).max(128),
    confirm_password: z.string().min(1),
  })
  .refine((data) => data.admin_password === data.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

type SignupFormData = z.infer<typeof signupSchema>;

const PRIMARY_BUTTON_CLASS =
  "flex h-11 w-full items-center justify-center rounded-[10px] bg-[linear-gradient(180deg,#12B568_0%,#0A9A65_30%,#068A63_62%,#048B78_86%,#019299_100%)] text-[13.5px] font-bold text-white shadow-[0_10px_20px_-10px_rgba(6,128,86,0.55)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_14px_26px_-10px_rgba(6,128,86,0.65)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:translate-y-0";

/**
 * Facility registration, in the same layout as the sign-in page with the
 * Create Account tab active. Submits the hospital/clinic account request
 * through the real backend API, and keeps every facility's data separated by
 * its own tenant.
 *
 * @returns The facility registration page
 */
export default function FacilitySignupPage() {
  const t = useTranslations("auth");
  const signup = useFacilitySignup();
  const [done, setDone] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
    defaultValues: { facility_type: "clinic" },
  });

  const onSubmit = async (data: SignupFormData) => {
    try {
      const { confirm_password: _confirm, ...payload } = data;
      void _confirm;
      const res = await signup.mutateAsync({
        ...payload,
        county: data.county || null,
        mfl_code: data.mfl_code || null,
        facility_phone: data.facility_phone || null,
        admin_password: data.admin_password,
      });
      setDone(res.message);
    } catch {
      // surfaced via signup.isError below
    }
  };

  const fieldClass = AUTH_INPUT_CLASS;
  const labelClass = AUTH_LABEL_CLASS;

  const handleGoogleSignIn = () => {
    setNotice(t("googleNotConnected"));
  };

  const focusAdminEmail = () => {
    setNotice(null);
    setFocus("admin_email");
  };

  return (
    <AuthShell>
      <AuthMiniBrand />

      <div className="mt-4 text-center">
        <h2 className="text-[21px] font-extrabold tracking-tight text-[#0B2E52]">
          {t("registerFacility")}
        </h2>
        <p className="mt-1 text-[12.5px] font-medium text-[#66788B]">
          {t("signupSubtitle")}
        </p>
      </div>

      <div className="mt-4">
        <AuthTabs mode="signup" />
      </div>

      {done ? (
        <div className="mt-8 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-[#0B8F79]" />
          <h3 className="mt-3 text-[19px] font-extrabold text-[#0B2E52]">
            {t("signupReceivedTitle")}
          </h3>
          <p className="mt-2 text-[13px] leading-relaxed text-[#64768A]">
            {done}
          </p>
          <Link
            href="/login"
            className="group mt-6 inline-flex items-center gap-2 rounded-[12px] bg-[linear-gradient(180deg,#12B568_0%,#0A9A65_45%,#068A63_100%)] px-5 py-2.5 text-[13.5px] font-bold text-white shadow-[0_14px_26px_-12px_rgba(6,128,86,0.55)] transition-all duration-200 hover:-translate-y-0.5"
          >
            {t("backToSignIn")}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      ) : (
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
              onClick={focusAdminEmail}
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

          <form onSubmit={handleSubmit(onSubmit)} className={AUTH_PANEL_CLASS}>
            <p className={AUTH_SECTION_TITLE_CLASS}>
              <Building2 className="h-3.5 w-3.5 text-[#0F8B6D]" />
              {t("facilityDetails")}
            </p>

            <div className="grid grid-cols-1 gap-3.5">
              <div>
                <label className={labelClass}>{t("facilityName")} *</label>
                <input
                  {...register("facility_name")}
                  placeholder="e.g. Aifya County Hospital"
                  className={fieldClass}
                />
                {errors.facility_name && (
                  <p className="mt-1 text-xs font-semibold text-[#E11D48]">
                    {t("required")}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-x-3.5 gap-y-3.5 sm:grid-cols-2">
                <div>
                  <label className={labelClass}>{t("facilityType")} *</label>
                  <select {...register("facility_type")} className={fieldClass}>
                    <option value="hospital">{t("typeHospital")}</option>
                    <option value="clinic">{t("typeClinic")}</option>
                    <option value="health_centre">{t("typeHealthCentre")}</option>
                    <option value="dispensary">{t("typeDispensary")}</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>{t("county")}</label>
                  <input {...register("county")} className={fieldClass} />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-x-3.5 gap-y-3.5 sm:grid-cols-2">
                <div>
                  <label className={labelClass}>{t("mflCode")}</label>
                  <input {...register("mfl_code")} className={fieldClass} />
                </div>
                <div>
                  <label className={labelClass}>{t("facilityPhone")}</label>
                  <input
                    {...register("facility_phone")}
                    placeholder="0712345678"
                    className={fieldClass}
                  />
                  {errors.facility_phone && (
                    <p className="mt-1 text-xs font-semibold text-[#E11D48]">
                      {errors.facility_phone.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="border-t border-[#E6EDF2] pt-3.5">
                <p className={AUTH_SECTION_TITLE_CLASS}>
                  <Sparkles className="h-3.5 w-3.5 text-[#0F8B6D]" />
                  {t("adminAccount")}
                </p>

                <div className="grid grid-cols-1 gap-x-3.5 gap-y-3.5 sm:grid-cols-2">
                  <div>
                    <label className={labelClass}>{t("firstName")} *</label>
                    <input {...register("admin_first_name")} className={fieldClass} />
                  </div>
                  <div>
                    <label className={labelClass}>{t("lastName")} *</label>
                    <input {...register("admin_last_name")} className={fieldClass} />
                  </div>
                </div>

                <div className="mt-3.5">
                  <label className={labelClass}>{t("adminEmail")} *</label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8FA6B5]" />
                    <input
                      {...register("admin_email")}
                      type="email"
                      autoComplete="email"
                      className={`${fieldClass} pl-10`}
                    />
                  </div>
                  {errors.admin_email && (
                    <p className="mt-1 text-xs font-semibold text-[#E11D48]">
                      {t("invalidEmail")}
                    </p>
                  )}
                </div>

                <div className="mt-3.5 grid grid-cols-1 gap-x-3.5 gap-y-3.5 sm:grid-cols-2">
                  <div>
                    <label className={labelClass}>Create password *</label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8FA6B5]" />
                      <input
                        {...register("admin_password")}
                        type="password"
                        autoComplete="new-password"
                        placeholder="At least 8 characters"
                        className={`${fieldClass} pl-10`}
                      />
                    </div>
                    {errors.admin_password && (
                      <p className="mt-1 text-xs font-semibold text-[#E11D48]">
                        {errors.admin_password.message}
                      </p>
                    )}
                  </div>
                  <div>
                    <label className={labelClass}>Confirm password *</label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#8FA6B5]" />
                      <input
                        {...register("confirm_password")}
                        type="password"
                        autoComplete="new-password"
                        placeholder="Repeat your password"
                        className={`${fieldClass} pl-10`}
                      />
                    </div>
                    {errors.confirm_password && (
                      <p className="mt-1 text-xs font-semibold text-[#E11D48]">
                        {errors.confirm_password.message}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {signup.isError && (
              <div className="mt-3.5 rounded-[10px] border border-[#FECDD3] bg-[#FFF1F2] px-3.5 py-2.5 text-[13px] font-semibold text-[#BE123C]">
                {signup.error?.message || t("signupError")}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting || signup.isPending}
              className={`${PRIMARY_BUTTON_CLASS} mt-3.5`}
            >
              {isSubmitting || signup.isPending ? (
                <span className="flex items-center gap-2.5">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  {t("submitting")}
                </span>
              ) : (
                t("requestAccount")
              )}
            </button>

            <p className="mt-3 text-center text-[13px] font-medium text-[#64768A]">
              {t("haveAccount")}{" "}
              <Link
                href="/login"
                className="font-extrabold text-[#0F8B6D] underline-offset-4 transition-colors hover:text-[#05614C] hover:underline"
              >
                {t("signInCta")}
              </Link>
            </p>
          </form>
        </>
      )}
    </AuthShell>
  );
}