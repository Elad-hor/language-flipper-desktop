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

### Either way — two traps that cost an hour on 2026-08-13

**1. Non-secret values belong in `wrangler.jsonc`, not the dashboard.**
`wrangler deploy` treats that file as the source of truth and **replaces all
plain-text variables** with whatever it declares. A `MAILGUN_DOMAIN` set in the
dashboard therefore works right up until the next push, then silently vanishes.
Secrets are stored separately and survive. `MAILGUN_DOMAIN` and `CONTACT_FROM`
now live in `wrangler.jsonc` for exactly this reason.

**2. A secret added in the dashboard is not live until something deploys.**
Cloudflare uses versioned deployments, so saving a secret creates a new version;
the running version keeps the old configuration. Trigger a build (push anything)
or deploy from the Deployments tab. Until then the form keeps reporting the
secret as missing, and it looks like the key was entered wrong.

The key must be a **Secret**, not a Text variable — otherwise it is readable in
the dashboard, can surface in build logs, and gets wiped by the next deploy.

If the form returns `Send failed: no mail provider configured (...)`, the
booleans in that message say exactly which piece the *running* Worker can see.

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

## 6. Hostinger cleanup — OPTIONAL, and probably not worth doing

**Status: cut over 2026-08-13.** The routes intercept every request before it
reaches Hostinger, so nothing there is being served.

**Deleting these files is not required.** The account still hosts other projects
being migrated separately, so the plan has to stay regardless — and cancelling the
plan later removes everything in one go. Meanwhile the files cost nothing and act
as a **free rollback**: delete the two Worker routes and Hostinger serves a working
site again instantly. Delete the files and that safety net is gone.

So the recommendation is: **leave them, and cancel the plan once every project has
moved off.**

If you do want to clean up early, the exact list follows.

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

## 7. Rolling back

> **EXPIRES 2026-08-24.** The Hostinger plan ends that day and is not being renewed,
> which takes the origin with it. **After that date, deleting the routes does not roll
> back — it takes the site down**, because `185.224.137.92` no longer serves anything of
> ours. Do not follow the instructions below after 2026-08-24.
>
> Two follow-ups once the plan lapses:
> * **Repoint the A record.** It still aims at an IP that Hostinger will reassign to
>   another customer. The routes intercept everything today, so nothing reaches the
>   origin — but a route that is later removed, edited or mis-scoped would send traffic
>   to a stranger's server under this domain and its certificate. Either attach the
>   Worker as a **Custom Domain** (the reason for preferring routes is gone once there is
>   nothing to roll back to) or park the record on a placeholder such as `192.0.2.1`.
> * Nothing else of ours lives there: no database, no mailbox, no cron. The domain is
>   registered at **Cloudflare** (expires 2027-05-05) and DNS is on Cloudflare
>   nameservers, so neither depends on the hosting plan.

Delete the two routes: **Workers → language-flipper-desktop → Settings → Domains
& Routes**. The `languageflipper.com` A record was never touched — it still points
at Hostinger (`185.224.137.92`, proxied) — so Hostinger resumes serving
**immediately, with no DNS propagation**. That is the whole reason routes were used
instead of a Workers Custom Domain.

DNS snapshot taken before the cutover:

```
A      languageflipper.com        -> 185.224.137.92        proxied
CNAME  www.languageflipper.com    -> languageflipper.com   proxied
MX     mg.languageflipper.com     -> mxa/mxb.mailgun.org   dns-only
TXT    mg.languageflipper.com     -> v=spf1 include:mailgun.org ~all
TXT    k1._domainkey.mg…          -> (DKIM)
TXT    languageflipper.com        -> google-site-verification=…
```

## 8. Loose ends

- `site/contact/contact.php` and `site/DEPLOY.md` are kept **on purpose** — they are
  what a full return to Hostinger would need. Delete them only when the Hostinger
  files go.
- The `/contact.php` route in `worker/index.ts` can go once no cached copy of the
  old HTML is plausibly still in use. Until then it stops a mid-flight submission
  hitting a 404.
- GitHub secrets `FTP_SERVER` / `FTP_USERNAME` / `FTP_PASSWORD` are unused now.
- Rotate the Mailgun API key; it was pasted into a chat during setup.
