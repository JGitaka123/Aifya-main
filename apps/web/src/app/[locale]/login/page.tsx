import { getBackendApiBase, isKeycloakAuthEnabled } from "@/lib/auth/config";

import LoginForm from "./LoginForm";

// The provider comes from the environment at request time, so this page must
// not be prerendered with a stale answer.
export const dynamic = "force-dynamic";

/** One state of duty the sign-in form can offer. */
interface DutyOption {
  role: string;
  label: string;
}

/**
 * Fetch the states of duty the API recognises.
 *
 * The catalogue lives with the role matrix on the API, so the form never keeps
 * a second copy that can drift from the one the sign-in check uses. A failure
 * here leaves the picker empty and the form falls back to a free-text field;
 * sign-in itself is still the API's to refuse.
 *
 * @returns The duty options, or an empty list when the API cannot be reached
 */
async function loadDuties(): Promise<DutyOption[]> {
  try {
    const response = await fetch(`${getBackendApiBase()}/auth/duties`, {
      cache: "no-store",
    });
    if (!response.ok) return [];
    const data = (await response.json()) as { duties?: DutyOption[] };
    return data.duties ?? [];
  } catch {
    return [];
  }
}

/**
 * Sign-in page.
 *
 * Renders the same branded shell whichever way the deployment signs people in.
 * The difference is whether the form posts credentials to Aifya's own API
 * (internal) or hands the browser to Keycloak (keycloak). The decision is made
 * on the server so the browser never has to guess which flow is in force.
 *
 * @returns The sign-in page
 */
export default async function LoginPage() {
  const duties = await loadDuties();

  return (
    <LoginForm
      keycloakEnabled={isKeycloakAuthEnabled()}
      duties={duties}
    />
  );
}
