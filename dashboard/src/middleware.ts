import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  // Skip auth for API routes that might be used internally
  if (req.nextUrl.pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  const basicAuth = req.headers.get("authorization");
  const url = req.nextUrl;

  if (basicAuth) {
    const authValue = basicAuth.split(" ")[1];
    const [user, pwd] = atob(authValue).split(":");

    // Get credentials from environment variables
    const validUser = process.env.AUTH_USERNAME || "admin";
    const validPassword = process.env.AUTH_PASSWORD || "password";

    if (user === validUser && pwd === validPassword) {
      return NextResponse.next();
    }
  }

  // Return 401 with WWW-Authenticate header to trigger browser basic auth popup
  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Ayejax Dashboard", charset="UTF-8"',
    },
  });
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
