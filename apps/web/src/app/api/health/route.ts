import { NextResponse } from "next/server";

/**
 * Liveness probe for the container health check.
 *
 * It sits under /api on purpose: the matcher in src/middleware.ts skips
 * /api, so the probe answers without a session cookie. A health check that
 * redirected to the login page would look healthy while the app was broken.
 *
 * @returns 200 with a small JSON body
 */
export function GET(): NextResponse {
  return NextResponse.json({ status: "ok" });
}
