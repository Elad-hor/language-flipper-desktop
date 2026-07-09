# Design: Rebuild languageflipper.com as a Prompt-Editable Static Site

**Date:** 2026-07-09
**Status:** Approved (design), pending spec review
**Author:** Elad + Claude

---

## 1. Goal

Rebuild the existing marketing site at `https://languageflipper.com/` as a
**pixel-for-pixel replica** built from code that lives in this git repository.

The purpose is to change *how the site is edited*: today the site is built in
WordPress + Elementor and every change is made by hand in the Elementor visual
editor. After this rebuild, every change ("add a For Dummies section", "change
the hero text", "add a new page") is made by **prompting Claude**, who edits the
source code, rebuilds, and redeploys. Elementor is retired.

**Non-goals:**
- Redesigning or improving the site. This is a faithful replica, not a redesign.
  Improvements come later, as separate prompted changes.
- Changing hosting, DNS, or the domain. Everything stays where it is.

---

## 2. Current-State Facts (captured 2026-07-09)

- **Platform:** WordPress + Hello Elementor theme + Elementor page builder
  (`elementor-kit-6`, `page-id-14` home).
- **Host:** origin responds with `platform: hostinger`, `x-powered-by: PHP/8.3.30`.
  Strong signal the WordPress files live on **Hostinger** shared hosting. To be
  confirmed by the owner at deploy time (via wherever `wp-admin` is managed) —
  not a blocker for the build.
- **DNS / CDN:** **Cloudflare** (nameservers `isaac`/`alexandra.ns.cloudflare.com`)
  proxying to the origin. Stays untouched.
- **Language / direction:** `lang="en-US"`, base `dir="ltr"`, with a full Hebrew
  mirror under `/he/…` (e.g. `/he/בית`) which is RTL.
- **Pages (exact URLs — must be preserved for SEO):**
  - `/` — home (dark purple theme; hero with background photo + gradient,
    "How it works", "Download Now" icon row, 4-card "Our solution" grid,
    "The Hard Truth" section, "Get the feeling" CTA, footer)
  - `/about-us`
  - `/solutions`
  - `/flip-it` — the interactive "try it" page
  - `/contact-us` — contact form
  - `/terms-of-service`
  - `/privacy-policy`
  - Hebrew mirror of the above under `/he/…`
  - `/wp-content/uploads/2026/05/accessibility-statement-EN.pdf` — accessibility
    statement PDF (carried over as a static asset)
- **Contact form (Elementor):** fields First Name, Last Name, Email (required),
  Company (required), Message → Submit. Currently posts to WordPress/Elementor
  which emails the site admin.
- **Interactive widget:** the repo already contains
  `marketing-site/try-it-widget.html` — a self-contained EN↔HE flip demo. This
  powers (or will power) the `/flip-it` page and ports directly into the rebuild.

---

## 3. Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Where site lives | **Code in this git repo** (new `site/` dir) | Enables prompt-driven editing + version control |
| Build tool | **Astro** static-site generator | Reusable components so 7 pages × 2 languages don't duplicate markup 14×; outputs plain static HTML; ships zero JS by default |
| Hosting | **Unchanged** — same host WordPress is on now (Hostinger) | User asked to keep hosting where it is |
| DNS | **Unchanged** — Cloudflare | No reason to touch it |
| Contact form backend | **PHP script on the existing host** → emails `falafeltikikunim@gmail.com` | Host already runs PHP 8.3; no third party, no serverless needed |
| Fidelity | **1:1 pixel replica** | Explicit user requirement |

---

## 4. Architecture

```
site/                        ← new Astro project (the rebuilt site)
  src/
    components/              ← Header, Footer, Nav, Button, DownloadRow,
                               SolutionCard, Hero, LanguageSwitcher, TryItWidget …
    layouts/
      BaseLayout.astro       ← <html> shell, meta, fonts, LTR/RTL handling
    pages/
      index.astro            ← /
      about-us.astro
      solutions.astro
      flip-it.astro          ← embeds the Try-It widget
      contact-us.astro
      terms-of-service.astro
      privacy-policy.astro
      he/                    ← Hebrew mirror (RTL), same structure
    i18n/                    ← EN + HE copy strings, so both languages share
                               one set of components
    styles/                  ← global CSS: colors, gradients, fonts, tokens
  public/
    assets/                  ← all downloaded images/icons/backgrounds + the
                               accessibility PDF
  astro.config.mjs
  package.json

contact/
  contact.php                ← receives form POST, validates, emails Gmail

docs/superpowers/specs/…     ← this spec
```

**Component boundaries (each has one clear purpose):**
- `BaseLayout` — the HTML document shell; owns `<head>`, fonts, and sets
  `dir="ltr"|"rtl"` + `lang` based on the page's language. Consumers pass in a
  title, meta description, and page body.
- `Header` / `Footer` / `Nav` — site chrome, identical across pages, language-aware
  via i18n strings. Change once, applies everywhere.
- `Hero`, `DownloadRow`, `SolutionCard`, section blocks — presentational; take
  content as props, render markup. No cross-section state.
- `TryItWidget` — the existing self-contained flip demo, wrapped as a component.
- `LanguageSwitcher` — toggles between a page and its `/he/…` counterpart.
- `contact.php` — standalone backend; one job: validate a form POST and send an
  email. No coupling to the front-end beyond field names.

**Data flow:** content strings live in `i18n/` (EN + HE) → passed as props into
components → rendered to static HTML at build time. The only runtime JS is the
Try-It widget (client-side flip) and the contact form submit (POST to
`contact.php`). Everything else is static HTML/CSS.

---

## 5. Fidelity Process (how "1:1" is achieved)

1. **Capture** every page in both languages with a headless browser: exact copy,
   computed colors, gradients, font families/sizes, spacing, and layout.
2. **Download** every asset (hero photo, section backgrounds, icons, logo, PDF)
   into `site/public/assets/`.
3. **Rebuild** each page/section as Astro components using the captured values.
4. **Compare** rebuilt pages against the live site with side-by-side screenshots
   at desktop (1440px) and mobile widths, iterating until they match.
5. **Preserve** all outbound links exactly as captured — download links
   (Mac DMG / Windows EXE), Gumroad "Get Premium", social links, and the PDF.

---

## 6. Contact Form

- Front-end: same fields as today (First Name, Last Name, Email*, Company*,
  Message), same layout.
- Submit posts to `contact/contact.php` on the same host.
- `contact.php` validates inputs (required Email + Company, basic spam guard),
  then sends the submission to **falafeltikikunim@gmail.com**.
- Delivery: SMTP is preferred over PHP `mail()` for Gmail deliverability. This
  may require a Gmail App Password or the host's SMTP relay — to be confirmed
  during implementation. If credentials are unavailable, fall back to the host's
  `mail()` and note the deliverability caveat.

---

## 7. Deployment & Rollback

- Astro builds to a static `dist/` folder.
- Deploy = upload `dist/` (plus `contact.php`) into the host's web root
  (`public_html`), replacing the WordPress files. Method (FTP / SSH / hPanel File
  Manager) determined once the owner confirms host access.
- **Safety sequence:**
  1. Build and verify the static site locally (screenshot comparison).
  2. Take a **full backup** of the current WordPress site + database before any swap.
  3. Optionally stage the static site on a subpath/subdomain for a final live check.
  4. Swap `public_html` to the static build.
  5. Keep the WordPress backup for rollback.
- Cloudflare DNS is not changed. After swap, purge Cloudflare cache so visitors
  get the new site.
- **Access required from owner (deploy step only):** host login / FTP / SSH
  credentials. Not needed for the build-and-verify phase.

---

## 8. Future Editing Workflow

After launch, a change follows this loop:
1. Owner prompts Claude (e.g. "add a For Dummies section to the home page").
2. Claude edits the relevant Astro component(s), rebuilds, redeploys.
3. Change is committed to git (full history + rollback).

No Elementor, no visual editor, no WordPress admin.

---

## 9. Open Items (confirmed during implementation, not blockers)

- Exact font family/families (EN + Hebrew) — captured from live site.
- Precise download-link targets (GitHub release URLs) and Gumroad link.
- Whether the Hebrew pages are full translations or partial — mirror exactly
  whatever exists.
- Host confirmation + access method for deploy.
- Contact-form email delivery method (SMTP creds vs `mail()`).

---

## 10. Risks

- **Host uncertainty:** the host is inferred, not confirmed. Mitigated because the
  build is host-agnostic; only the final upload depends on it.
- **Replacing WordPress is destructive:** mitigated by full backup + verify-before-swap
  + retained rollback.
- **i18n / RTL fidelity:** Hebrew RTL layout must match exactly; handled by
  capturing and mirroring the live pages rather than guessing.
- **Asset/content drift:** the Try-It widget's inlined character map is a manual
  copy of `en_he_map.json`; note the same drift risk applies to any content
  copied from the app into the site.
