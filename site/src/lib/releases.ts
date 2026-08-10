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
 * Used when the API is unreachable (offline dev, GitHub outage, rate limit).
 * The build must never fail or emit an empty href because of a network blip —
 * a stale link is bad, a broken one is worse.
 */
const FALLBACK: Record<Platform, Download> = {
  mac: {
    url: `https://github.com/${REPO}/releases/download/v0.1.67-mac/Language.Flipper.dmg`,
    version: '0.1.67',
  },
  win: {
    url: `https://github.com/${REPO}/releases/download/v0.1.105-windows/Language-Flipper-Setup.exe`,
    version: '0.1.105',
  },
};

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

// The component renders on 6 pages; fetch once per build, not six times.
let cached: Promise<Record<Platform, Download>> | null = null;

async function fetchDownloads(): Promise<Record<Platform, Download>> {
  const headers: Record<string, string> = {
    'User-Agent': 'languageflipper-site-build',
    Accept: 'application/vnd.github+json',
  };
  // CI runners share IPs and hit the 60/hour unauthenticated limit; the token
  // GitHub Actions provides automatically raises that to 1000/hour.
  const token = process.env.GITHUB_TOKEN;
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100`, { headers });
  if (!res.ok) throw new Error(`GitHub API ${res.status}`);
  const releases = (await res.json()) as GhRelease[];

  const out = { ...FALLBACK };
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
    if (best) out[platform] = best;
  }
  return out;
}

export function getDownloads(): Promise<Record<Platform, Download>> {
  if (!cached) {
    cached = fetchDownloads().catch((err) => {
      // Warn loudly in the build log, but keep building.
      console.warn(`[releases] falling back to pinned download URLs: ${err}`);
      return FALLBACK;
    });
  }
  return cached;
}
