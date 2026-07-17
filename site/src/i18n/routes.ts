// EN ↔ HE route pairs, used to emit hreflang alternates and the language switcher.
// Paths are the final (trailing-slash) URLs as built. HE paths use literal Hebrew
// directory names; they are percent-encoded when turned into absolute URLs.
export const routePairs: ReadonlyArray<{ en: string; he: string | null }> = [
  { en: '/', he: '/he/בית/' },
  { en: '/about-us/', he: '/he/עלינו/' },
  { en: '/flip-it/', he: '/he/תפליפו/' },
  { en: '/contact-us/', he: '/he/צור-קשר/' },
  { en: '/terms-of-service/', he: '/he/תנאי-שימוש/' },
  { en: '/privacy-policy/', he: '/he/פרטיות/' },
  { en: '/solutions/', he: null }, // EN only — no Hebrew mirror
];

// Decode so we can match against Astro.url.pathname (which is already decoded).
function norm(p: string): string {
  try {
    return decodeURIComponent(p);
  } catch {
    return p;
  }
}

/**
 * Given the current pathname, return the EN and HE counterparts (or null when a
 * language has no equivalent page). Falls back to the current path as its own EN
 * entry so unmapped pages still get a self-referencing canonical/hreflang.
 */
export function alternatesFor(pathname: string): { en: string | null; he: string | null } {
  const path = norm(pathname);
  for (const pair of routePairs) {
    if (norm(pair.en) === path || (pair.he && norm(pair.he) === path)) {
      return { en: pair.en, he: pair.he };
    }
  }
  return { en: path, he: null };
}
