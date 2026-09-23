import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  BETA_PUBLIC_ACCESS_ENABLED,
  getBetaUser,
} from "@/lib/auth/beta";
import { getBackendApiBase } from "@/lib/auth/config";

/**
 * Report the signed-in user, or 401 when there is no usable session.
 *
 * @returns The authenticated user, or { authenticated: false }
 */
export async function GET(): Promise<NextResponse> {
  if (BETA_PUBLIC_ACCESS_ENABLED) {
    return NextResponse.json({
      authenticated: true,
      user: getBetaUser(),
    });
  }

  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }

  try {
    const response = await fetch(`${getBackendApiBase()}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return NextResponse.json({ authenticated: false }, { status: 401 });
    }
    const data = (await response.json()) as {
      authenticated?: boolean;
      user?: Record<string, unknown>;
    };
    return NextResponse.json({
      authenticated: true,
      user: data.user ?? {},
    });
  } catch {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }
}