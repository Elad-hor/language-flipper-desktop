# Moving languageflipper.com off Hostinger → Cloudflare Workers

**Goal:** stop serving the site from Hostinger, without changing anything users see.

**Scope:** remove **only** the Language Flipper files. The Hostinger account also
holds other projects and old sites, being migrated separately — do not cancel the
plan, and do not delete anything not listed in section 6.

**Why it's low-risk:** DNS is already fully on Cloudflare (`alexandra`/`isaac.ns.cloudflare.com`)
and the site is proxied, so visitors never touch Hostinger's IP. There are **no MX
records** on the domain, so no email depends on this host.

**Why Workers and not Pages:** Cloudflare has put Pages into maintenance and routes
new Git-connected projects through Workers, which is what the dashboard offers.
Workers Static Assets serves the built site and honours `_headers` and `_redirects`
just as Pages did — confirmed locally (`✨ Parsed 5 valid redirect rules. ✨ Parsed
2 valid header rules.`).

---

## 1. Create the Worker

Cloudflare dashboard → **Compute (Workers & Pages)** → **Create application** →
**Import a repository** → connect GitHub → pick `language-flipper-desktop`.

Build settings:

| Field | Value |
|---|---|
| Project name | `language-flipper-desktop` (must match `name` in `wrangler.jsonc`) |
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |
| **Path** (under **Advanced settings**) | **`/site`** |

**"Path" is the root-directory field.** Workers Builds doesn't call it "root
directory" the way Pages did, and it's hidden behind *Advanced settings*, defaulting
to `/`. Left at `/`, the build fails: `package.json`, `wrangler.jsonc` and the Astro
project all live in `site/`.

Everything else (`name`, entry point, the assets binding) is already in
`site/wrangler.jsonc` — leave the defaults alone and it will read that file.

Non-production branch builds need no changes.

## 2. Give the contact form a mail provider

The form ran on PHP `mail()` at Hostinger. There is no PHP here, so it posts to the
Worker, which hands the message to **either Mailgun or Resend** — whichever is
configured. Mailgun wins if both are.

Set these in the Worker → **Settings → Variables and Secrets**, then redeploy.

### Option A — Mailgun

| Name | Type | Value |
|---|---|---|
| `MAILGUN_API_KEY` | **Secret** | private API key |
| `MAILGUN_DOMAIN` | Text | sending domain, e.g. `mg.languageflipper.com` |
| `MAILGUN_API_BASE` | Text | **EU accounts only:** `https://api.eu.mailgun.net` |

**If the account is in the EU region, `MAILGUN_API_BASE` is not optional.** An EU
domain hitting the default US endpoint returns **401**, which looks exactly like a
wrong API key.

Note the free plan caps API keys (2) and asks for a card.

### Option B — Resend

| Name | Type | Value |
|---|---|---|
| `RESEND_API_KEY` | **Secret** | API key with *Sending access* |

Free tier is 3,000/month with no card. Add `languageflipper.com` under
**Domains**, put the DKIM/SPF records it gives you into Cloudflare DNS, and verify —
otherwise mail from `no-reply@languageflipper.com` is rejected.

### Either way

The key must be a **Secret**, not a Text variable, or it is readable in the
dashboard and can surface in build logs.

Optional overrides: `CONTACT_TO` (default `falafeltikunim@gmail.com`) and
`CONTACT_FROM` (default `Language Flipper <no-reply@languageflipper.com>` — must be
on the verified sending domain).

From the terminal instead:
```bash
cd site && npx wrangler secret put MAILGUN_API_KEY    # or RESEND_API_KEY
```

## 3. Verify on the workers.dev URL — before touching DNS

The Worker gets a URL like `language-flipper.elad-05d.workers.dev`. Test there; the
real domain is still on Hostinger and unaffected.

Most of this is already automated — run it against the deployed URL:

```bash
cd site && node capture/scripts/verify-worker.mjs      # runs against a local worker
```

By hand on the live workers.dev URL:

- [ ] All 13 pages load (7 EN + 6 Hebrew under `/he/…`), Hebrew is RTL
- [ ] `/attributes`, `/category/uncategorized` → `/` (301); `/sitemap_index.xml` →
      `/sitemap-index.xml` (301)
- [ ] `curl -sI <url>/ | grep -i cache-control` → `public, max-age=0, must-revalidate`
- [ ] `curl -sI <url>/_astro/<any>.js | grep -i cache-control` →
      `public, max-age=31536000, immutable` **and nothing else on the line**
- [ ] **Submit the contact form**: the email arrives, the page returns with the green
      success banner, and a Hebrew submission comes back to the Hebrew page

## 4. Point the domain at the Worker

Worker → **Settings → Domains & Routes → Add → Custom domain** →
`languageflipper.com`, then again for `www.languageflipper.com`. Cloudflare rewrites
the DNS records itself, since it already manages the zone.

Repeat the section 3 checks on the real domain, and submit the form once more.

## 5. Stop the FTP deploy

`.github/workflows/deploy.yml` still uploads to Hostinger on every push — leave it
running and it will recreate the files you are about to delete. Delete the workflow
(the Worker deploys on push by itself) and remove the now-unused repo secrets
`FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`.

## 6. Remove the Language Flipper files from Hostinger

**Only after sections 4 and 5.** Give it a day or two first: until these files are
gone, rolling back is just a DNS change.

In hPanel → File Manager, in the web root Language Flipper was deployed to, delete
**exactly these** — the complete list of what the deploy ever wrote:

```
_astro/                          about-us/
assets/                          contact-us/
he/                              flip-it/
                                 privacy-policy/
index.html                       solutions/
favicon.svg                      terms-of-service/
llms.txt
robots.txt
sitemap-0.xml
sitemap-index.xml
accessibility-statement-EN.pdf
accessibility-statement-HE.pdf
_headers        (inert on Apache; only ever ignored)
_redirects      (same)
contact.php
.htaccess
```

**Check `.htaccess` before deleting it.** The deploy overwrote it with Language
Flipper's rules only, so it should contain nothing but the redirects and cache
blocks from `.github/workflows/deploy.yml`. If it holds anything else, something
outside this project depends on it — keep the file and remove only our sections.

**If another site shares this web root**, stop and check with whoever is migrating
it before deleting root-level files.

## 7. Afterwards

- `site/contact/contact.php` can be deleted from the repo — kept for now as the
  rollback path while Hostinger still serves the site.
- The `/contact.php` route in `worker/index.ts` can go once no cached copy of the
  old HTML is plausibly still in use. Until then it prevents a mid-flight
  submission hitting a 404.
- `site/DEPLOY.md` documents the Hostinger/FTP process and becomes obsolete.
