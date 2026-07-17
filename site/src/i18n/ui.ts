import en from './en.json';
import he from './he.json';

export const languages = { en: 'English', he: 'עברית' };

export type Lang = keyof typeof languages;

export const rtl = new Set<Lang>(['he']);

export const defaultLang: Lang = 'en';

const translations: Record<Lang, Record<string, string>> = { en, he };

export function t(lang: Lang, key: string): string {
  return translations[lang]?.[key] ?? translations[defaultLang]?.[key] ?? key;
}

export function dir(lang: Lang): 'ltr' | 'rtl' {
  return rtl.has(lang) ? 'rtl' : 'ltr';
}
