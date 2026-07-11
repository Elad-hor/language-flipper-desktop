# Deploying the Marketing Site

The marketing site (`languageflipper.com`) is a static [Astro](https://astro.build) site in `site/`.
Deploying = build it to static files and put them where the current WordPress files live.
**Hosting (Hostinger) and DNS (Cloudflare) do not change** — only the files in the web root change.

> ⚠️ This replaces the live WordPress site. Do the **backup + verify** steps first. Keep the
> WordPress backup until you're confident, so you can roll back.

---

## 1. Build

```bash
cd site
npm install          # first time only
npm run build        # outputs static site to site/dist/
```

`dist/` contains all 13 pages (7 EN + 6 Hebrew RTL) as plain HTML/CSS/JS + `assets/` + the two accessibility PDFs.

Preview locally before deploying:
```bash
npm run preview      # http://localhost:4321/
```

## 2. Back up the current live site (DO THIS FIRST)

On the host (Hostinger hPanel or wherever WordPress is managed):
- Export the WordPress **database** (phpMyAdmin → Export, or hPanel backup).
- Download a **zip of `public_html/`** (the whole current web root).
- Store both off-host. Confirm the zip opens and the DB dump is non-empty.

This is the rollback point. Do not skip it.

## 3. (Recommended) Stage before swapping

Upload `dist/` to a temporary subfolder or a staging subdomain first (e.g. `public_html/_new/`)
and load it directly on the real host to sanity-check fonts, images, and the contact form POST.

## 4. Deploy

Put the built files into the web root (`public_html/`), replacing the WordPress files:

- **Static site:** upload the **contents of `site/dist/`** into `public_html/`.
- **Contact backend:** upload **`site/contact/contact.php`** to the web root as **`public_html/contact.php`**
  (the contact form posts to `/contact.php`). It lives outside `dist/` on purpose — Astro doesn't process it.

Upload method depends on host access: hPanel File Manager, FTP/SFTP, or SSH `rsync`.

## 5. Contact form email

`contact.php` sends submissions to **falafeltikikunim@gmail.com** using PHP `mail()` (baseline).

If Gmail marks `mail()` messages as spam or drops them (common on shared hosting), switch to SMTP:
- Use the host's SMTP relay **or** a Gmail App Password, via PHPMailer or the host's mail settings.
- The HTML form and its `action="/contact.php"` do **not** change — only the send mechanism inside `contact.php`.
- Send a test submission and confirm it arrives before relying on it.

## 6. Go live + verify

- If you staged in a subfolder, move `dist/` contents to the real `public_html/` root.
- **Purge the Cloudflare cache** (Cloudflare dashboard → Caching → Purge Everything) so visitors get the new site.
- Verify every URL loads (EN + HE):
  `/`, `/about-us/`, `/solutions/`, `/flip-it/`, `/contact-us/`, `/terms-of-service/`, `/privacy-policy/`,
  `/he/בית/`, `/he/עלינו/`, `/he/צור-קשר/`, `/he/תפליפו/`, `/he/תנאי-שימוש/`, `/he/פרטיות/`
- Submit the contact form once and confirm the email arrives.

## 7. Rollback (if needed)

Re-upload the WordPress `public_html/` backup and re-import the database, then purge Cloudflare cache.

---

## Notes / known items

- `/solutions/` intentionally reproduces the live site's **404-style page** (the live URL currently serves
  a styled 404, not a real Solutions page). To make it a real page later, edit `site/src/pages/solutions.astro`.
- The hero headline is static; the original used an Elementor animated rotating headline (EN ↔ Hebrew).
  Cosmetic — add later if desired.
- The Try-It widget's character map is copied inline from `flipper_daemon/layouts/en_he_map.json`
  (in `site/src/components/TryItWidget.astro`); update it if the app's map changes.
- Future edits are code changes in `site/` — edit the component/page, `npm run build`, redeploy.
  No WordPress/Elementor involved.
