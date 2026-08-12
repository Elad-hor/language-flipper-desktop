# Moving languageflipper.com off Hostinger → Cloudflare Pages

**Goal:** stop serving the site from Hostinger, without changing anything users see.

**Scope:** remove **only** the Language Flipper files. The Hostinger account also
holds other projects and old sites, which are being migrated separately — do not
cancel the plan, and do not delete anything not listed in section 5.

**Why it's low-risk:** DNS is already fully on Cloudflare (`alexandra`/`isaac.ns.cloudflare.com`)
and the site is proxied, so visitors never touch Hostinger's IP. There are **no MX
records** on the domain, so no email depends on this host.

**The only real work** is the contact form: it runs on PHP `mail()`, and no static
host runs PHP. That's already ported (section 2).

---

## 1. Create the Cloudflare Pages project

Cloudflare dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
→ pick `Elad-hor/language-flipper-desktop`.

Build settings:

| Field | Value |
|---|---|
| Production branch | `main` |
| Framework preset | Astro |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `site` |

The **root directory must be `site`** — that's what makes Pages find both
`site/dist` and `site/functions/`.

## 2. Set up Resend (the contact form's mail sender)

1. Sign up at resend.com (free tier: 3,000 emails/month).
2. **Domains → Add Domain → `languageflipper.com`.** It gives you DKIM/SPF records
   to add in Cloudflare DNS. Add them, then click Verify.
   Without this, mail sent as `no-reply@languageflipper.com` is rejected.
3. **API Keys → Create**, with *Sending access* only. Copy the key.
4. In the Pages project → **Settings → Environment variables → Production**, add:

   | Name | Value |
   |---|---|
   | `RESEND_API_KEY` | the key from step 3 |

   Optional overrides, only if you want to change the defaults:
   `CONTACT_TO` (default `falafeltikunim@gmail.com`),
   `CONTACT_FROM` (default `Language Flipper <no-reply@languageflipper.com>`).

5. Redeploy so the variable is picked up.

## 3. Verify on the pages.dev URL — before touching DNS

Pages gives you `<project>.pages.dev`. Check there first; the real domain is
still on Hostinger and unaffected.

- [ ] All 13 pages load (7 EN + 6 Hebrew under `/he/…`)
- [ ] Hebrew pages are RTL and the fonts are right
- [ ] `/solutions/` (the FAQ) loads
- [ ] `/sitemap-index.xml` and `/robots.txt` load
- [ ] Redirects: `/attributes` and `/category/uncategorized` → home,
      `/sitemap_index.xml` → `/sitemap-index.xml` (all 301)
- [ ] **Submit the contact form** and confirm the email arrives, that the page
      returns with the green success banner, and that a Hebrew submission comes
      back to the Hebrew page
- [ ] Cache headers: HTML should be `no-cache`/`must-revalidate`,
      `/_astro/*` should be `immutable`

```bash
curl -sI https://<project>.pages.dev/ | grep -i cache-control
curl -sI https://<project>.pages.dev/_astro/<any>.js | grep -i cache-control
```

## 4. Cut DNS over

Pages project → **Custom domains** → add `languageflipper.com` and
`www.languageflipper.com`. Cloudflare rewrites the DNS records itself, since it
already manages the zone.

Then verify on the **real domain**: repeat the section 3 checklist, and submit the
contact form once more.

Watch it for a day or two. **Do not delete anything from Hostinger until you have.**
Rolling back is trivial until the files are gone: point the DNS records back.

## 5. Remove the Language Flipper files from Hostinger

Only after section 4 is confirmed good. In hPanel → File Manager, in the web root
that Language Flipper was deployed to, delete **exactly these** — the full list of
what the deploy ever wrote:

```
_astro/                     about-us/
assets/                     contact-us/
he/                         flip-it/
                            privacy-policy/
index.html                  solutions/
favicon.svg                 terms-of-service/
llms.txt
robots.txt
sitemap-0.xml
sitemap-index.xml
accessibility-statement-EN.pdf
accessibility-statement-HE.pdf
_headers                    (inert on Apache; only ever ignored)
_redirects                  (same)
contact.php
.htaccess
```

**Check `.htaccess` before deleting it.** The deploy overwrote it with Language
Flipper's rules only, so it *should* contain nothing but the three redirects and
the cache blocks documented in `.github/workflows/deploy.yml`. If it contains
anything else, something outside this project depends on it — keep it and remove
only our sections.

**If any other site shares this web root**, stop and check with whoever is
migrating it before deleting root-level files.

## 6. Turn off the FTP deploy

Once Pages is live, `.github/workflows/deploy.yml` should stop uploading to
Hostinger — otherwise every push rewrites the files you just deleted. Remove the
workflow (Pages deploys on push by itself) and delete the now-unused repo secrets
`FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`.

## 7. Afterwards

- `site/contact/contact.php` can be deleted from the repo — kept for now as the
  rollback path while Hostinger still serves the site.
- `site/functions/contact.php.ts` (the old-URL alias) can go once no cached copy
  of the old HTML is plausibly still in use.
- `site/DEPLOY.md` describes the Hostinger/FTP process and will be obsolete.
