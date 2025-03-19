import { NextFetchEvent, NextRequest, NextResponse } from "next/server";
import { CustomMiddleware } from "./chainMiddleware";
import { fallbackLng } from "@/lib/i18n/settings";

//paths that are shared by all tenants
const commonPaths = [
  "/logout",
  "/login",
  "/register",
  "/forgotPassword",
  "/resetPassword",
  "/activate",
  "/minio",
  "/google/callback",
  "/invoice",
];

export function withTenant(middleware: CustomMiddleware) {
  return async (req: NextRequest, event: NextFetchEvent, res: NextResponse) => {
    const url = req.nextUrl.clone();

    const pathWithoutLocale = url.pathname
      .replace("/en", "")
      .replace("/sk", "");

    const hostname = req.headers.get("host") || ""; // Get the hostname from the request
    const subdomain = hostname.split(".")[0]; // Parse the subdomain (assuming subdomain is the first part)

    let lng: string | undefined;
    const paths = url.pathname.split("/").filter((path) => path);
    if (paths[0]?.length === 2) {
      lng = paths.shift();
    } else lng = fallbackLng;

    if (commonPaths.some((path) => pathWithoutLocale === path)) {
      return middleware(req, event, res);
    }

    // Rewrite the response to include the subdomain in the path
    if (
      subdomain === "localhost:3000" &&
      process.env.NODE_ENV === "development"
    ) {
      const newUrl = new URL(
        `/${lng}/conferences/${paths.join("/")}${url.search}`,
        req.url
      ); // Rewrite the path with the subdomain

      return NextResponse.rewrite(newUrl, {
        headers: res?.headers,
      });
    }

    if (subdomain.includes("flawis")) {
      const newUrl = new URL(
        `/${lng}/flawis/${paths.join("/")}${url.search}`,
        req.url
      );

      return NextResponse.rewrite(newUrl, {
        headers: res?.headers,
      });
    }

    if (subdomain.includes("conferences")) {
      const newUrl = new URL(
        `/${lng}/conferences/${paths.join("/")}${url.search}`,
        req.url
      );

      return NextResponse.rewrite(newUrl, {
        headers: res?.headers,
      });
    }

    if (subdomain.includes("intern")) {
      const newUrl = new URL(
        `/${lng}/internships/${paths.join("/")}${url.search}`,
        req.url
      );

      return NextResponse.rewrite(newUrl, {
        headers: res?.headers,
      });
    }

    // Execute remaining middleware
    return middleware(req, event, res);
  };
}
