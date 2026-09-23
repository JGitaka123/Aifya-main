import { NextRequest, NextResponse } from "next/server";

const KNOWLEDGE_SERVICE_URL = (
  process.env.KNOWLEDGE_SERVICE_URL ?? "http://localhost:8025"
).replace(/\/$/, "");

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

/**
 * Proxy knowledge-service requests, converting the httpOnly session
 * cookie into the Bearer header the service expects. The browser cannot
 * read the cookie (by design), so direct calls to the service could
 * never authenticate.
 *
 * @param request - Incoming same-origin request
 * @param context - Route context with the wildcard path segments
 * @returns The knowledge-service response passed through
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
  const url = new URL(`${KNOWLEDGE_SERVICE_URL}/api/v1/${path.join("/")}`);
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
  } catch (error) {
    // The service is a separate container; a 502 here almost always means it
    // is not running (or is still starting), not that the request was bad.
    // Log the target so that is obvious in the dev server output.
    console.error(
      `[knowledge proxy] ${request.method} ${url.toString()} failed:`,
      error
    );
    return NextResponse.json(
      {
        detail:
          "Knowledge service unavailable. It runs as its own process, so it " +
          "has to be started separately from the API: run " +
          "scripts\\start-knowledge.ps1 (no Docker needed) and retry. " +
          `Tried ${url.origin}.`,
      },
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
