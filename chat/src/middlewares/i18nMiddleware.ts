import { NextFetchEvent, NextRequest, NextResponse } from "next/server";
import acceptLanguage from "accept-language";
import { cookieName, fallbackLng, languages } from "../lib/i18n/settings";
import { CustomMiddleware } from "./chainMiddleware";

acceptLanguage.languages(languages);

export function withLocalization(middleware: CustomMiddleware) {
  return (req: NextRequest, event: NextFetchEvent) => {
    const url = req.nextUrl.clone();
    const domain =
      process.env.NODE_ENV === "development" ? "localhost" : ".flaw.uniba.sk";

    let currentLng;
    if (req.cookies.has(cookieName))
      currentLng = acceptLanguage.get(req.cookies.get(cookieName)?.value);
    if (!currentLng)
      currentLng = acceptLanguage.get(req.headers.get("Accept-Language"));
    if (!currentLng) currentLng = fallbackLng;

    const paths = url.pathname.split("/");

    // Rewrite for default lng if no lng is in path
    if (!languages.some((loc) => url.pathname.startsWith(`/${loc}`))) {
      // Remove lng from path if it is not supported and redirect with currentLng
      if (paths[1].length === 2) {
        url.pathname = `/${currentLng}${url.pathname.slice(3)}`;

        return NextResponse.redirect(url);
        // Redirect if currentLng si supported but is missing in path
      } else if (currentLng !== fallbackLng) {
        url.pathname = `/${currentLng}${url.pathname}`;

        return NextResponse.redirect(url);
        // Rewrite when currentLng is fallbackLng
      } else {
        url.pathname = `/${currentLng}${url.pathname}`;

        return middleware(
          req,
          event,
          NextResponse.rewrite(url, {
            headers: {
              "Set-Cookie": `${cookieName}=${fallbackLng}; path=/; Domain=${domain}`,
            },
          })
        );
      }
    }

    // Remove default locale from path
    if (url.pathname.startsWith(`/${fallbackLng}`)) {
      url.pathname = url.pathname.slice(3);

      return NextResponse.redirect(url, {
        headers: {
          "Set-Cookie": `${cookieName}=${fallbackLng}; path=/; Domain=${domain}`,
        },
      });
    }

    const response = NextResponse.next();
    response.cookies.set(cookieName, paths[1], { domain });

    return middleware(req, event, response);
  };
}
