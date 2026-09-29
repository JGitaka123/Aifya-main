import { isKeycloakAuthEnabled } from "@/lib/auth/config";

import LoginForm from "./LoginForm";

// The provider comes from the environment at request time, so this page must
// not be prerendered with a stale answer.
export const dynamic = "force-dynamic";

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
export default function LoginPage() {
  return <LoginForm keycloakEnabled={isKeycloakAuthEnabled()} />;
}
