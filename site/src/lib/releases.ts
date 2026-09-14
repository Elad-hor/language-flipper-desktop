/**
 * Resolve the newest download URL per platform, at BUILD time.
 *
 * Why not GitHub's /releases/latest/download/<asset> shortcut: `latest` is a
 * single pointer across all releases, and this repo interleaves `-mac` and
 * `-windows` tags. When the newest release is a Windows one, asking it for
 * Language.Flipper.dmg 404s. Same reason flipper_daemon/updater.py scans the
 * full release list instead — see "Key Past Bugs" #5 in CLAUDE.md.
 *
 * So: fetch every release and pick the highest version that actually carries
 * the platform's asset — the same rule the in-app updater applies.
 *
 * ---------------------------------------------------------------------------
 * This module FAILS THE BUILD when it cannot resolve a URL. That is deliberate
 * and was learned the hard way, twice.
 *
 * It used to catch every error and silently substitute pinned constants. The
 * result: a broken resolver and a healthy one produced an identical-looking
 * site, so there was no signal anywhere that anything was wrong. On
 * 2026-09-14 the live Mac button was found serving v0.1.67 while the newest
 * published DMG was v0.1.111 — 44 versions stale, straight from the fallback
 * constants. It had been that way for an unknown number of builds. What kept
 * it invisible was luck: the pinned Windows fallback happened to equal the
 * true newest Windows release, so only one of the two buttons looked wrong.
 *
 * That is the exact shape of Key Past Bug #2, the macOS updater that failed
 * every single check for months behind a bare `except Exception: pass`.
 *
 * A failed build is loud and costs nothing — Cloudflare keeps serving the last
 * good deployment. A silently stale download link is invisible and ships users
 * an old app. So: retry what might be weather, then throw.
 * ---------------------------------------------------------------------------
 */

const REPO = 'Elad-hor/language-flipper-desktop';

const ASSET = {
  mac: 'Language.Flipper.dmg',
  win: 'Language-Flipper-Setup.exe',
} as const;

export type Platform = keyof typeof ASSET;

export interface Download {
  url: string;
  version: string;
}

/**
 * Escape hatch for working offline (`astro dev` on a train). Set
 * LF_ALLOW_STALE_DOWNLOADS=1 to get these pinned URLs instead of a hard
 * failure. Deliberately verbose to set and deliberately named "STALE": these
 * URLs are frozen in source and go out of date the moment anything ships, so
 * this must never be set in CI or in the Cloudflare build — that would
 * reinstate the silent-staleness bug this file exists to prevent.
 */
const STALE_FALLBACK: Record<Platform, Download> = {
  mac: {
    url: `https://github.com/${REPO}/releases/download/v0.1.111-mac/Language.Flipper.dmg`,
    version: '0.1.111',
  },
  win: {
    url: `https://github.com/${REPO}/releases/download/v0.1.105-windows/Language-Flipper-Setup.exe`,
    version: '0.1.105',
  },
};

// A build resolves this once and reuses it for every page, so spending a few
// seconds retrying is cheap insurance against a blip. Anything that survives
// all the attempts is a real fault, not weather.
const ATTEMPTS = 3;
const RETRY_BASE_MS = 1500;

/** "v0.1.105-windows" | "0.1.67" -> [0, 1, 105] */
function parseVersion(tag: string): number[] {
  const clean = tag.replace(/^v/, '').split('-')[0];
  const parts = clean.split('.').map((n) => Number.parseInt(n, 10));
  return parts.some(Number.isNaN) ? [0] : parts;
}

function isNewer(a: number[], b: number[]): boolean {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const x = a[i] ?? 0;
    const y = b[i] ?? 0;
    if (x !== y) return x > y;
  }
  return false;
}

interface GhAsset { name: string; browser_download_url: string }
interface GhRelease { tag_name: string; draft: boolean; prerelease: boolean; assets: GhAsset[] }

/** Thrown for a failure that more retrying cannot clear (e.g. a rate limit). */
class PermanentError extends Error {}

/**
 * Turn a non-OK response into a message that names the actual cause.
 *
 * "GitHub API 403" was the old text, and it is ambiguous exactly where it
 * matters: a 403 is both "rate limited" and "token rejected", and those need
 * completely different fixes. GitHub distinguishes them in the headers, so
 * read them.
 */
function describeFailure(res: Response, authenticated: boolean): { message: string; permanent: boolean } {
  const remaining = res.headers.get('x-ratelimit-remaining');
  const reset = res.headers.get('x-ratelimit-reset');
  const who = authenticated ? 'authenticated' : 'UNAUTHENTICATED (no GITHUB_TOKEN in this environment)';

  if ((res.status === 403 || res.status === 429) && remaining === '0') {
    const at = reset ? new Date(Number(reset) * 1000).toISOString() : 'an unknown time';
    return {
      // Retrying cannot help — the window is up to an hour wide.
      permanent: true,
      message:
        `GitHub API rate limit exhausted (${who}); resets at ${at}. ` +
        `Unauthenticated callers get 60 requests/hour PER IP, and shared CI ` +
        `or build-runner IPs burn that between them. Fix: set a GITHUB_TOKEN ` +
        `build variable (a read-only classic token with no scopes is enough ` +
        `for public release metadata), which raises the limit to 5000/hour.`,
    };
  }

  if (res.status === 401) {
    return { permanent: true, message: `GitHub API 401 — GITHUB_TOKEN is set but was rejected (expired or revoked?).` };
  }

  return { permanent: res.status >= 400 && res.status < 500, message: `GitHub API ${res.status} ${res.statusText} (${who})` };
}

async function fetchReleases(): Promise<GhRelease[]> {
  const headers: Record<string, string> = {
    'User-Agent': 'languageflipper-site-build',
    Accept: 'application/vnd.github+json',
  };
  // GITHUB_TOKEN is provided automatically by GitHub Actions but NOT by
  // Cloudflare Workers Builds, where it has to be set as a build variable.
  const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100`, { headers });
  if (!res.ok) {
    const { message, permanent } = describeFailure(res, Boolean(token));
    throw permanent ? new PermanentError(message) : new Error(message);
  }
  return (await res.json()) as GhRelease[];
}

async function resolveDownloads(): Promise<Record<Platform, Download>> {
  const releases = await fetchReleases();
  const out = {} as Record<Platform, Download>;

  for (const platform of Object.keys(ASSET) as Platform[]) {
    let bestVer: number[] | null = null;
    let best: Download | null = null;

    for (const release of releases) {
      if (release.draft || release.prerelease) continue;
      const asset = (release.assets ?? []).find((a) => a.name === ASSET[platform]);
      if (!asset) continue;
      const ver = parseVersion(release.tag_name);
      if (bestVer && !isNewer(ver, bestVer)) continue;
      bestVer = ver;
      best = { url: asset.browser_download_url, version: ver.join('.') };
    }

    // Reaching the API and finding nothing is also a failure worth stopping
    // for — it means the asset was renamed, or every release carrying it is
    // marked prerelease. Emitting a button with no href is not a better
    // outcome than a red build.
    if (!best) {
      throw new PermanentError(
        `no published (non-draft, non-prerelease) release carries ${ASSET[platform]} — renamed asset, or all such releases flagged prerelease?`,
      );
    }
    out[platform] = best;
  }

  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function resolveOrFail(): Promise<Record<Platform, Download>> {
  let last: unknown;
  let tried = 0;

  for (let attempt = 1; attempt <= ATTEMPTS; attempt++) {
    tried = attempt;
    try {
      return await resolveDownloads();
    } catch (err) {
      last = err;
      if (err instanceof PermanentError) break; // more tries cannot help
      if (attempt < ATTEMPTS) {
        console.warn(`[releases] attempt ${attempt}/${ATTEMPTS} failed: ${err}; retrying`);
        await sleep(RETRY_BASE_MS * attempt);
      }
    }
  }

  const reason = last instanceof Error ? last.message : String(last);
  // `tried`, not ATTEMPTS: a PermanentError stops after one go, and claiming
  // three would send someone hunting for two retries that never happened.
  const tally = tried === 1 ? '1 attempt' : `${tried} attempts`;

  if (process.env.LF_ALLOW_STALE_DOWNLOADS === '1') {
    console.warn(
      `\n[releases] ###########################################################\n` +
        `[releases] USING STALE PINNED DOWNLOAD URLS — do not deploy this build.\n` +
        `[releases] reason: ${reason}\n` +
        `[releases] mac -> ${STALE_FALLBACK.mac.version}, win -> ${STALE_FALLBACK.win.version}\n` +
        `[releases] ###########################################################\n`,
    );
    return STALE_FALLBACK;
  }

  throw new Error(
    `[releases] could not resolve download URLs after ${tally}: ${reason}\n` +
      `\n` +
      `  Failing the build on purpose. The download buttons would otherwise ship\n` +
      `  silently stale links, which is how the live Mac button spent an unknown\n` +
      `  number of builds pointing at v0.1.67 while v0.1.111 was current.\n` +
      `  Cloudflare keeps serving the last good deployment, so nothing is down.\n` +
      `\n` +
      `  To build offline anyway: LF_ALLOW_STALE_DOWNLOADS=1 npm run build\n`,
  );
}

// The component renders on 6 pages; resolve once per build, not six times.
let cached: Promise<Record<Platform, Download>> | null = null;

export function getDownloads(): Promise<Record<Platform, Download>> {
  if (!cached) cached = resolveOrFail();
  return cached;
}
