import { chain } from "./middlewares/chainMiddleware";
import { withLocalization } from "./middlewares/i18nMiddleware";

export const config = {
  // do not localize next.js paths and public folder
  matcher: [
    "/((?!api|_next|favicon.ico|images|UKsans|site.webmanifest|browserconfig.xml|sw.js|.pdf).*)",
  ],
};

export default chain([withLocalization]);
