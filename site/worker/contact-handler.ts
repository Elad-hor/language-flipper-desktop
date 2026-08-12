/**
 * Contact form handler — the replacement for contact.php.
 *
 * Hostinger ran the form through PHP mail(); a static host has no PHP, so this
 * runs in a Cloudflare Worker and hands the message to Mailgun instead.
 *
 * Behaviour is deliberately identical to the PHP version, because the form
 * markup and the success banner both depend on it:
 *   - POST only
 *   - honeypot field `website`; if filled, pretend success and send nothing
 *   - `email` required and valid, `company` required
 *   - reject CR/LF in header-bound fields (header injection)
 *   - redirect back to `redirect` + "?sent=1", where ContactForm.astro reveals
 *     the success banner client-side. Hebrew submissions carry their own
 *     Hebrew path, which is why the redirect is echoed rather than hardcoded.
 *   - only same-site absolute paths are accepted as a redirect target, so this
 *     can't be turned into an open redirect
 *
 * Routed from worker/index.ts for both /contact and /contact.php: the old
 * .php route is kept alive so no cached page or bookmark breaks during the
 * move off Hostinger.
 */

export interface ContactEnv {
  /** Mailgun private API key. A secret — never in wrangler.jsonc. */
  MAILGUN_API_KEY: string;
  /** The sending domain as configured in Mailgun, e.g. mg.languageflipper.com. */
  MAILGUN_DOMAIN: string;
  /**
   * Mailgun region endpoint. EU accounts MUST set this to
   * https://api.eu.mailgun.net — the US default returns 401 for EU domains,
   * which looks exactly like a bad API key.
   */
  MAILGUN_API_BASE?: string;
  /** Optional overrides; the defaults match the PHP version. */
  CONTACT_TO?: string;
  CONTACT_FROM?: string;
}

const DEFAULT_TO = 'falafeltikunim@gmail.com';
// Must be on the Mailgun sending domain, or delivery is rejected.
const DEFAULT_FROM = 'Language Flipper <no-reply@languageflipper.com>';
const DEFAULT_API_BASE = 'https://api.mailgun.net';

function textResponse(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}

/** Same rule as the PHP: a same-site absolute path, no protocol-relative, no CR/LF. */
function safeRedirect(raw: unknown): string {
  if (typeof raw !== 'string') return '/contact-us/';
  if (raw === '' || raw[0] !== '/' || raw.startsWith('//') || /[\r\n]/.test(raw)) {
    return '/contact-us/';
  }
  return raw;
}

function isEmail(value: string): boolean {
  // Intentionally permissive, matching FILTER_VALIDATE_EMAIL's practical effect:
  // reject the obviously malformed, don't try to out-clever RFC 5322.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export async function handleContact(request: Request, env: ContactEnv): Promise<Response> {
  if (request.method !== 'POST') return textResponse(405, 'Method not allowed');

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return textResponse(400, 'Bad request');
  }

  const str = (k: string) => String(form.get(k) ?? '').trim();

  const redirect = safeRedirect(form.get('redirect'));
  const success = `${redirect}?sent=1`;

  // Honeypot: bots fill it, humans never see it. Report success, send nothing.
  if (str('website') !== '') return Response.redirect(new URL(success, request.url).toString(), 302);

  const first = str('first_name');
  const last = str('last_name');
  const email = str('email');
  const company = str('company');
  const message = str('message');

  if (email === '' || !isEmail(email)) return textResponse(422, 'Valid email required');
  if (company === '') return textResponse(422, 'Company required');
  for (const v of [first, last, email, company]) {
    if (/[\r\n]/.test(v)) return textResponse(422, 'Invalid input');
  }

  if (!env.MAILGUN_API_KEY || !env.MAILGUN_DOMAIN) {
    // Loud, because a silently unconfigured form loses real enquiries.
    console.error('MAILGUN_API_KEY / MAILGUN_DOMAIN not set — cannot send contact email');
    return textResponse(500, 'Send failed');
  }

  const subject = `Language Flipper contact from ${first !== '' ? first : 'website'}`;
  const body =
    `Name: ${first} ${last}\n` +
    `Email: ${email}\n` +
    `Company: ${company}\n\n` +
    `Message:\n${message}\n`;

  // Mailgun's messages endpoint takes form-encoded fields and HTTP Basic auth
  // with the literal username "api".
  const params = new URLSearchParams({
    from: env.CONTACT_FROM || DEFAULT_FROM,
    to: env.CONTACT_TO || DEFAULT_TO,
    subject,
    text: body,
    // So hitting reply in Gmail answers the visitor, not the robot.
    'h:Reply-To': email,
  });

  const base = (env.MAILGUN_API_BASE || DEFAULT_API_BASE).replace(/\/+$/, '');
  const url = `${base}/v3/${encodeURIComponent(env.MAILGUN_DOMAIN)}/messages`;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Basic ${btoa(`api:${env.MAILGUN_API_KEY}`)}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    });

    if (!res.ok) {
      // 401 here usually means the region is wrong (an EU domain hit the US
      // endpoint) rather than a bad key — see MAILGUN_API_BASE.
      console.error(`Mailgun rejected the message: ${res.status} ${await res.text()}`);
      return textResponse(500, 'Send failed');
    }
  } catch (err) {
    console.error(`Mailgun request failed: ${err}`);
    return textResponse(500, 'Send failed');
  }

  return Response.redirect(new URL(success, request.url).toString(), 302);
}
