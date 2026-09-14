/**
 * Common Hebrew words and what they look like typed on an English layout.
 *
 * These strings are not decoration — they are search queries. Search Console
 * shows `dhcrha` (גיבריש) at position 8.8 with more impressions than any
 * Hebrew phrase on the site, and `dhcrha kgcrh,` (גיבריש לעברית) next to it.
 * People type a word with the keyboard still in English, see nonsense, and
 * paste that nonsense straight into Google. yo-yoo.co.il has held first place
 * for years partly by putting `akuo שלום` in its title tag.
 *
 * GENERATED from flipper_daemon/layouts/en_he_map.json via
 * flipper_daemon/flipper.py — the same mapping the app ships, so the strings
 * on the page are exactly what the app produces. Four of these were wrong when
 * typed by hand, so regenerate rather than editing: tests/test_gibberish_data.py
 * fails the build if this file and the map ever disagree.
 */
export interface GibPair {
  /** The Hebrew word the person meant to type. */
  he: string;
  /** What actually appeared, with the keyboard still in English. */
  gib: string;
}

export const GIBBERISH_PAIRS: readonly GibPair[] = [
  { he: 'גיבריש', gib: 'dhcrha' },
  { he: 'שלום', gib: 'akuo' },
  { he: 'תודה', gib: ',usv' },
  { he: 'בבקשה', gib: 'cceav' },
  { he: 'סליחה', gib: 'xkhjv' },
  { he: 'מה קורה', gib: 'nv eurv' },
  { he: 'בוקר טוב', gib: 'cuer yuc' },
  { he: 'ערב טוב', gib: 'grc yuc' },
  { he: 'לילה טוב', gib: 'khkv yuc' },
  { he: 'מקלדת', gib: 'neks,' },
  { he: 'עברית', gib: 'gcrh,' },
  { he: 'אנגלית', gib: 'tbdkh,' },
  { he: 'מחשב', gib: 'njac' },
  { he: 'טלפון', gib: 'ykpui' },
  { he: 'אהבה', gib: 'tvcv' },
  { he: 'בית', gib: 'ch,' },
  { he: 'משפחה', gib: 'napjv' },
  { he: 'עבודה', gib: 'gcusv' },
  { he: 'כן', gib: 'fi' },
  { he: 'לא', gib: 'kt' },
  { he: 'בסדר', gib: 'cxsr' },
  { he: 'מעולה', gib: 'ngukv' },
  { he: 'להתראות', gib: 'kv,rtu,' },
  { he: 'נתראה', gib: 'b,rtv' },
] as const;
