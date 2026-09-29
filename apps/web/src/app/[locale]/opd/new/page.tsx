import { redirect } from "@/i18n/routing";

interface OpdNewRedirectProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * The retired OPD "new visit" desk.
 *
 * Opening a visit and taking the consultation fee is the front desk's job, so
 * this route no longer renders a second registration screen. It forwards to
 * Registration - the single front-desk entry point - carrying whoever the
 * caller had already picked, so old links and bookmarks still land correctly.
 *
 * @param props.params - Route params carrying the active locale
 * @param props.searchParams - Query string carrying the selected patient
 * @returns Never - the response is a redirect
 */
export default async function OpdNewRedirect({
  params,
  searchParams,
}: OpdNewRedirectProps) {
  const { locale } = await params;
  const query = await searchParams;

  const carried: Record<string, string> = {};
  for (const key of ["patient_id", "patient_name"] as const) {
    const value = query[key];
    if (typeof value === "string" && value) carried[key] = value;
  }

  redirect({
    href:
      Object.keys(carried).length > 0
        ? { pathname: "/patients/register", query: carried }
        : "/patients/register",
    locale,
  });
}
