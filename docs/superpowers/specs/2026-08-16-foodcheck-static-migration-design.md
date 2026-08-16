# foodcheck.co.il → static Astro on Cloudflare

**Status:** approved 2026-08-16, implementation deliberately deferred. Elad will say when to start.
**Lives here temporarily** — this belongs in the `foodcheck-site` repo once that exists.

## Why

The Hostinger Business plan lapses **2026-08-24** and is not being renewed. foodcheck.co.il is a
live WordPress site on it (WordPress 6.9.7, Elementor 4.0.6, PHP 8.3, LiteSpeed) and dies with the
plan. It is being rebuilt as a static site on Cloudflare, the same move languageflipper.com made on
2026-08-13 — see `site/MIGRATION.md` for the version of this that has already been survived once.

## What the site actually is

Established by inspection on 2026-08-16:

- **5 pages:** `/`, `/about-us/`, `/solutions/`, `/certified-copy/`, `/contact-us/`
- 1 stray post `/attributes/`, 1 empty `uncategorized` category
- **English only** (`lang="en-US"`) — no Hebrew mirror, unlike Language Flipper
- **One Elementor contact form** on `/contact-us/` (name, email, two text fields)
- No shop, no logins, no WooCommerce. A brochure site.
- Home ~114 KB, contact ~69 KB of HTML

## Decisions

| Question | Decision |
|---|---|
| Purpose after the move | A **living site**, prompt-editable like languageflipper.com — so a real Astro rebuild, not a scraped copy |
| Design | **Faithful.** Rebuild the current look; visitors notice nothing. No redesign decisions on the clock |
| Where the code lives | **Its own repo** (`foodcheck-site`), its own Worker. No coupling to Language Flipper |
| DNS | Moves to **Cloudflare** (free, required for a Worker to serve the domain) |
| Contact form | Worker + **Mailgun**, new sending domain `mg.foodcheck.co.il`, delivered to the existing **Purelymail** inbox |

## Step 0 — capture, before 2026-08-24

**The only part with a real deadline.** Everything — text, images, fonts, rendered CSS — is gone
when the plan lapses. Full `wget` mirror plus screenshots of all 5 pages at desktop and mobile
widths, committed as reference material. Once captured, the rebuild can happen calmly, even after
the 24th.

## Architecture

Same shape as `site/`, which is proven: Astro static output, a Cloudflare Worker serving the
assets, `wrangler.jsonc`, Workers Builds deploying on push to `main`.

**Design fidelity without Elementor's CSS.** Extract the real colours, fonts, spacing and imagery
from the live site; rebuild clean Astro components that match visually. Elementor's compiled CSS is
hundreds of KB of generated bloat and would fight every future edit — which defeats the point of a
site meant to be edited by prompt.

**Routing.** Trailing slashes preserved so existing links and search results keep working.
WordPress cruft (`/feed/`, `/wp-json/`, `/xmlrpc.php`, the empty category) is dropped, with 301s
where anything might be linked.

**Contact form.** Ported from `site/worker/contact-handler.ts`: POST-only, honeypot, required
fields, CR/LF header-injection guard, same-site-path-only redirect with `?sent=1`.

Purelymail is where mail *arrives* and does not change. It cannot *send* the form: Purelymail sends
over SMTP, and Cloudflare Workers cannot speak SMTP — port 25 is blocked and there is no practical
SMTP client in that runtime. Hence Mailgun's HTTP API as the courier, delivering into Purelymail.
**Do not use a Mailgun sandbox domain** — Gmail accepts sandbox mail then flags `DMARC:Quarantine`
and it lands in spam. Verify `mg.foodcheck.co.il` properly, as was done for `mg.languageflipper.com`.

**Cutover.** Nameservers to Cloudflare → build and verify on `*.workers.dev` → attach the domain as
a **Custom Domain**, not zone routes. Language Flipper used routes specifically to keep an instant
Hostinger rollback; there is no rollback to preserve here, so the trick doesn't apply.

**Verification.** Port the check scripts: pages return 200, ported redirects work, cache headers
correct, contact-form failure modes self-describing. Same pattern as
`site/capture/scripts/verify-worker.mjs`.

## Needed from Elad

1. Change foodcheck.co.il's nameservers to Cloudflare at Hostinger (I have no DNS access)
2. Mailgun sending-domain setup for `mg.foodcheck.co.il`
3. The destination address for form submissions

## The DNS zone as it stands (dumped from ns1.dns-parking.com, 2026-08-16)

Recreate **all of these in Cloudflare first**, verify, and only then change the nameservers at
InterSpace. Done in that order there is no gap and mail never stops.

| Name | Type | Value | Proxy | Keep |
|---|---|---|---|---|
| `foodcheck.co.il` | MX | `50 mailserver.purelymail.com` | DNS only | **critical** |
| `foodcheck.co.il` | TXT | `v=spf1 include:_spf.purelymail.com ~all` | DNS only | **critical** |
| `foodcheck.co.il` | TXT | `purelymail_ownership_proof=6f2ac4a66f1df0be72833d209d5e4259b57f4f05ba3b772a921601472b5c851149dc15a9cb4ea436b039dbfb5f0e7e82e0f912b5a0191f56114317deb99ba4f3` | DNS only | **critical** |
| `_dmarc` | CNAME | `dmarcroot.purelymail.com` | **DNS only** | **critical** |
| `purelymail1._domainkey` | CNAME | `key1.dkimroot.purelymail.com` | **DNS only** | **critical** |
| `purelymail2._domainkey` | CNAME | `key2.dkimroot.purelymail.com` | **DNS only** | **critical** |
| `purelymail3._domainkey` | CNAME | `key3.dkimroot.purelymail.com` | **DNS only** | **critical** |
| `foodcheck.co.il` | TXT | `google-site-verification=1VUQtDMMl10lEy9mWxheevf1-vM9-4J4paXfiD5ZWd0` | DNS only | keep |
| `foodcheck.co.il` | A | `185.224.137.92` | Proxied | temporary — dies with Hostinger |
| `foodcheck.co.il` | AAAA | `2a02:4780:8:1224:0:1ede:76e8:5` | Proxied | temporary — same |
| `www` | CNAME | `foodcheck.co.il` | Proxied | keep |
| `ftp` | A | `185.224.137.92` | — | drop, Hostinger only |
| `autodiscover` | CNAME | `autodiscover.mail.hostinger.com` | — | drop, stale (mail is Purelymail) |
| `autoconfig` | CNAME | `autoconfig.mail.hostinger.com` | — | drop, stale |

No CAA, no wildcard, nothing else in the zone.

**The DKIM and DMARC records are CNAMEs and Cloudflare defaults CNAMEs to proxied.** A proxied
`_domainkey` breaks DKIM lookups, and the symptom appears a week later as mail landing in spam.
Grey cloud on all four.

**Check the delegation actually took, on BOTH nameservers.** Reported by the session handling
whattoeat.co.il: the InterSpace form applied only one of the two, leaving one Cloudflare
nameserver alongside one `dns-parking.com` one. A half-delegation keeps working, so nothing looks
wrong. Verify in whois after the change, not just by loading the site:

```
dig NS foodcheck.co.il +short            # expect BOTH Cloudflare nameservers, no dns-parking
dig MX foodcheck.co.il +short
dig CNAME purelymail1._domainkey.foodcheck.co.il +short
```

## Security check before mirroring

whattoeat.co.il — same server (185.224.137.92), same Elementor stack, and linked from
whattoeat's footer — **was compromised**: roughly 1,425 injected `/NNNNNNN.htm` doorway pages
serving 200 through 2025, advertised by five phantom `sitemapNNN.xml` entries still listed in its
robots.txt.

foodcheck.co.il was checked for the same signature on 2026-08-16 and looks **clean**: guessed
`/NNNNNNN.htm` paths all 404, `robots.txt` lists one legitimate sitemap, `sitemap1-5.xml` all 404.

That is a surface check from outside, not proof. **Re-verify at mirror time**: the mirror must
follow only the 5 known pages and the sitemap, and any URL that appears in the crawl but not in the
inventory above is to be treated as suspect and excluded rather than carried into the new site.

## Known traps, inherited from the last migration

- Plain-text vars belong in `wrangler.jsonc`, not the dashboard — `wrangler deploy` replaces all
  plain vars, so dashboard-set values vanish on the next push. Secrets survive.
- There are **two** "Variables and Secrets" screens; the one reachable from Settings is the *build*
  one, which the Worker cannot read. Use `npx wrangler secret put`.
- No `/*` rule in `_headers` — Cloudflare combines matching rules rather than letting the specific
  one win, which emits two `max-age` values and breaks asset caching.
- `compatibility_date` must not exceed the workerd build in the installed wrangler.
- Verification scripts must spawn servers as **foreground** children; the sandbox reaps backgrounded
  ones.
