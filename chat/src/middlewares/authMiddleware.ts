import { NextFetchEvent, NextRequest, NextResponse } from "next/server";
import { CustomMiddleware } from "./chainMiddleware";

const publicPaths = [
  "/login",
  "/register",
  "/forgotPassword",
  "/resetPassword",
  "/google/callback",
];

export function withAuth(middleware: CustomMiddleware) {
  return async (req: NextRequest, event: NextFetchEvent, res: NextResponse) => {
    const url = req.nextUrl.clone();
    const pathWithoutLocale = url.pathname
      .replace("/en", "")
      .replace("/sk", "");
    const token = req.cookies.get("accessToken")?.value;

    if (!token && !publicPaths.some((path) => path === pathWithoutLocale)) {
      const loginUrl = new URL("/login", url.origin);

      if (url.pathname !== "/" && url.pathname !== "/logout") {
        const originalUrl = `${url.pathname}${url.search}`;
        loginUrl.searchParams.set("url", originalUrl);
      }

      return NextResponse.redirect(loginUrl);
    }

    if (token && publicPaths.some((path) => path === pathWithoutLocale)) {
      let redirectTo = "/";
      const referer = req.headers.get("referer");

      if (referer) {
        // Use the referer header to extract a clean target URL.
        const refererUrl = new URL(referer);
        // In case the referer contains an encoded "url" parameter, decode it:
        const urlParam = refererUrl.searchParams.get("url");
        if (urlParam) {
          redirectTo = decodeURIComponent(urlParam);
        } else if (!publicPaths.some((path) => path === pathWithoutLocale)) {
          redirectTo = `${refererUrl.pathname}${refererUrl.search}`;
        }
      }
      const finalUrl = new URL(redirectTo, url.origin);

      return NextResponse.redirect(finalUrl);
    }

    return middleware(req, event, res);
  };
}
