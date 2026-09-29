import { NextResponse } from "next/server";

import {
  getAppBaseUrl,
  getKeycloakClientId,
  getKeycloakIssuer,
  getLoginPageUrl,
  isKeycloakAuthEnabled,
} from "@/lib/auth/config";
import { buildEndSessionUrl } from "@/lib/auth/oidc";
import { getSessionCookieDomain } from "@/lib/auth/session";

/**
 * End the session and return the user to the sign-in page.
 *
 * In keycloak mode this also has to end the session at Keycloak: clearing only
 * our own cookies would leave the SSO cookie alive, so the next sign-in would
 * silently re-authenticate the same person.
 *
 * @returns A redirect to the sign-in page (via Keycloak when in use) with the
 *          session cookies cleared
 */
export async function GET(): Promise<NextResponse> {
  const domain = getSessionCookieDomain();
  const loginUrl = `${getAppBaseUrl()}${getLoginPageUrl()}`;

  const target = isKeycloakAuthEnabled()
    ? buildEndSessionUrl({
        issuer: getKeycloakIssuer(),
        clientId: getKeycloakClientId(),
        postLogoutRedirectUri: loginUrl,
      })
    : loginUrl;

  const response = NextResponse.redirect(target);
  // Clear the cookies with the same domain scope they were set with, so a
  // parent-domain (COOKIE_DOMAIN) cookie is actually removed.
  response.cookies.set("access_token", "", { path: "/", maxAge: 0, domain });
  response.cookies.set("refresh_token", "", { path: "/", maxAge: 0, domain });
  return response;
}
