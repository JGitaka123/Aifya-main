import { NextRequest, NextResponse } from "next/server";

const SCRIBE_SERVICE_URL = (
  process.env.SCRIBE_SERVICE_URL ?? "http://localhost:8005"
).replace(/\/$/, "");

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

/**
 * Proxy scribe-service requests, converting the httpOnly session cookie
 * into the Bearer header the service expects. The scribe backend accepts
 * platform Keycloak (RS256) tokens alongside its own local tokens.
 *
 * @param request - Incoming same-origin request
 * @param context - Route context with the wildcard path segments
 * @returns The scribe-service response passed through
 */
async function proxy(
  request: NextRequest,
  context: RouteContext
): Promise<NextResponse> {
  const token = request.cookies.get("access_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const { path } = await context.params;
  const url = new URL(`${SCRIBE_SERVICE_URL}/api/v1/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token}`);
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const init: RequestInit = { method: request.method, headers };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = Buffer.from(await request.arrayBuffer());
  }

  try {
    const response = await fetch(url, init);
    const responseHeaders = new Headers();
    const responseType = response.headers.get("content-type");
    if (responseType) {
      responseHeaders.set("content-type", responseType);
    }
    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "Scribe service unavailable" },
      { status: 502 }
    );
  }
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as DELETE,
};
