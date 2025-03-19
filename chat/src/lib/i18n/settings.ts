export const fallbackLng = "sk";
export const languages = [fallbackLng, "en"];
export const defaultNS = "translation";
export const cookieName = "NEXT_locale";

export function getOptions(
  lng = fallbackLng,
  ns = [defaultNS] as string | string[]
) {
  return {
    // debug: true,
    supportedLngs: languages,
    fallbackLng,
    lng,
    fallbackNS: defaultNS,
    defaultNS,
    ns,
  };
}
