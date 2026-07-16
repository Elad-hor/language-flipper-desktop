// Reusable Schema.org JSON-LD builders for page-specific structured data.
// Site-wide Organization + WebSite live in Seo.astro; these are passed per page
// via the BaseLayout `schema` prop.
import type { Lang } from './i18n/ui';

const SITE = 'https://languageflipper.com';

/** SoftwareApplication with the freemium offer set. Localised description. */
export function softwareApplication(lang: Lang) {
  const description =
    lang === 'he'
      ? 'אפליקציית שולחן עבודה ל-macOS ול-Windows שמתקנת בלחיצת מקש טקסט שנכתב בפריסת מקלדת שגויה — ממירה בין עברית לאנגלית באופן מיידי.'
      : 'A macOS and Windows desktop app that instantly fixes text typed in the wrong keyboard layout, converting between Hebrew and English with a single hotkey.';
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Language Flipper',
    url: SITE,
    applicationCategory: 'UtilitiesApplication',
    operatingSystem: 'macOS, Windows',
    description,
    inLanguage: lang === 'he' ? 'he' : 'en',
    offers: [
      {
        '@type': 'Offer',
        name: lang === 'he' ? 'חינמי' : 'Free',
        price: '0',
        priceCurrency: 'USD',
      },
      {
        '@type': 'Offer',
        name: lang === 'he' ? 'פרמיום' : 'Premium',
        price: '9.99',
        priceCurrency: 'USD',
      },
    ],
    publisher: { '@id': `${SITE}/#organization` },
  };
}

/** Two-level breadcrumb: Home > current page. `home` label/url localised by caller. */
export function breadcrumb(
  home: { name: string; url: string },
  current: { name: string; url: string },
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: home.name, item: home.url },
      { '@type': 'ListItem', position: 2, name: current.name, item: current.url },
    ],
  };
}

/** FAQPage from a list of {q, a}. */
export function faqPage(lang: Lang, qas: Array<{ q: string; a: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    inLanguage: lang === 'he' ? 'he' : 'en',
    mainEntity: qas.map(({ q, a }) => ({
      '@type': 'Question',
      name: q,
      acceptedAnswer: { '@type': 'Answer', text: a },
    })),
  };
}
